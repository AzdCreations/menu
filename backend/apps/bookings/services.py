"""Бизнес-логика записи: свободные окна, создание записи, смена статусов (раздел 5 ТЗ)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.catalog.models import Membership, Venue
from apps.core.exceptions import ApiError, Conflict
from apps.core.models import Setting
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import Booking, BookingEvent

S = Booking.Status
N = Notification.Type


# --------------------------------------------------------------------------- окна


def venue_tz(venue):
    return ZoneInfo(venue.timezone)


def local_today(venue, now=None):
    return (now or timezone.now()).astimezone(venue_tz(venue)).date()


def _parse_time(value):
    return datetime.strptime(value, "%H:%M").time()


def _subtract(intervals, holes):
    """Вычитает из отсортированных интервалов [start, end) интервалы holes."""
    result = []
    for start, end in intervals:
        pieces = [(start, end)]
        for hole_start, hole_end in holes:
            next_pieces = []
            for p_start, p_end in pieces:
                if hole_end <= p_start or hole_start >= p_end:
                    next_pieces.append((p_start, p_end))
                    continue
                if hole_start > p_start:
                    next_pieces.append((p_start, hole_start))
                if hole_end < p_end:
                    next_pieces.append((hole_end, p_end))
            pieces = next_pieces
        result.extend(pieces)
    return result


def working_windows(membership, day):
    """Рабочие интервалы специалиста на дату с учётом исключений, графика заведения и перерывов."""
    venue = membership.venue
    tz = venue_tz(venue)

    exceptions = list(membership.exceptions.filter(date_from__lte=day, date_to__gte=day))
    if any(exc.kind == exc.Kind.DAY_OFF for exc in exceptions):
        return []
    custom = next((exc for exc in exceptions if exc.start and exc.end), None)
    if custom:
        start, end, breaks = custom.start, custom.end, []
    else:
        hours = next((wh for wh in membership.working_hours.all() if wh.weekday == day.weekday()), None)
        if hours is None:
            return []
        start, end, breaks = hours.start, hours.end, hours.breaks or []

    venue_hours = next((vh for vh in venue.hours.all() if vh.weekday == day.weekday()), None)
    if venue_hours is not None:
        if venue_hours.is_day_off:
            return []
        if venue_hours.start and venue_hours.end:
            start, end = max(start, venue_hours.start), min(end, venue_hours.end)
    if start >= end:
        return []

    def at(t):
        return datetime.combine(day, t, tzinfo=tz)

    holes = [(at(_parse_time(b["start"])), at(_parse_time(b["end"]))) for b in breaks]
    return _subtract([(at(start), at(end))], sorted(holes))


def busy_q(now):
    """Записи, которые реально занимают время: подтверждённые и непросроченные заявки."""
    return Q(status=S.CONFIRMED) | Q(status=S.PENDING) & (Q(respond_by__isnull=True) | Q(respond_by__gt=now))


def available_slots(membership, service, day, now=None):
    """Список начал свободных окон (aware datetime) для услуги на дату."""
    now = now or timezone.now()
    today = local_today(membership.venue, now)
    if day < today or day > today + timedelta(days=membership.horizon_days):
        return []

    windows = working_windows(membership, day)
    if not windows:
        return []

    buffer = timedelta(minutes=membership.buffer_minutes)
    day_start, day_end = windows[0][0], windows[-1][1]
    busy = (
        Booking.objects.filter(specialist_id=membership.specialist_id, start__lt=day_end + buffer, end__gt=day_start - buffer)
        .filter(busy_q(now))
        .values_list("start", "end")
    )
    free = _subtract(windows, sorted((s - buffer, e + buffer) for s, e in busy))

    step = membership.slot_step_minutes
    duration = timedelta(minutes=service.duration_minutes)
    earliest = now + timedelta(minutes=membership.min_lead_minutes)
    tz = venue_tz(membership.venue)
    midnight = datetime.combine(day, datetime.min.time(), tzinfo=tz)

    slots = []
    for free_start, free_end in free:
        begin = max(free_start, earliest)
        minutes = (begin - midnight).total_seconds() / 60
        aligned = int(-(-minutes // step) * step)  # округление вверх до шага сетки
        slot = midnight + timedelta(minutes=aligned)
        while slot + duration <= free_end:
            slots.append(slot)
            slot += timedelta(minutes=step)
    return slots


# --------------------------------------------------------------------------- запись


def format_when(booking):
    return booking.start.astimezone(venue_tz(booking.venue)).strftime("%d.%m %H:%M")


def _params(booking):
    return {
        "venue": booking.venue.name,
        "service": booking.service_name or "—",
        "when": format_when(booking),
        "client": booking.client_name or (booking.client.name if booking.client else "") or "—",
    }


def _log(booking, old, actor, reason=""):
    BookingEvent.objects.create(booking=booking, old_status=old, new_status=booking.status, actor=actor, reason=reason)


def _save_new(booking, actor):
    """Сохраняет запись; пересечение по времени превращается в 409 slot_taken."""
    try:
        with transaction.atomic():
            booking.save()
    except IntegrityError as exc:
        if "booking_no_overlap_per_specialist" in str(exc):
            raise Conflict("slot_taken", "Это время уже занято.") from exc
        raise
    _log(booking, "", actor)


def validate_extra(category, extra):
    extra = extra or {}
    clean = {}
    for field in category.booking_fields or []:
        key = field.get("key")
        value = extra.get(key)
        if value in (None, ""):
            if field.get("required"):
                raise ApiError("extra_required", f"Заполните поле «{field.get('label_ru', key)}».")
            continue
        kind = field.get("type", "text")
        if kind == "bool" and not isinstance(value, bool):
            raise ApiError("extra_invalid", f"Поле «{field.get('label_ru', key)}»: ожидается да/нет.")
        if kind == "select" and value not in field.get("options", []):
            raise ApiError("extra_invalid", f"Поле «{field.get('label_ru', key)}»: выберите значение из списка.")
        if kind == "text":
            value = str(value)[:500]
        clean[key] = value
    return clean


def client_no_show_count(client, now):
    return Booking.objects.filter(client=client, status=S.NO_SHOW, start__gte=now - timedelta(days=90)).count()


def create_client_booking(client, membership, service, start, comment="", extra=None):
    now = timezone.now()
    venue = membership.venue
    if membership.status != Membership.Status.ACCEPTED or venue.status != Venue.Status.APPROVED:
        raise ApiError("specialist_unavailable", "Специалист сейчас не принимает записи.")
    if service.membership_id != membership.id or not service.is_active:
        raise ApiError("service_unavailable", "Услуга недоступна.")
    if membership.specialist_id == client.id:
        raise ApiError("self_booking", "Нельзя записаться к самому себе.")

    pending = Booking.objects.filter(client=client, status=S.PENDING, respond_by__gt=now).count()
    if pending >= Setting.get("max_pending_per_client"):
        raise ApiError("too_many_pending", "Слишком много заявок ждут подтверждения.")

    day = start.astimezone(venue_tz(venue)).date()
    if start not in available_slots(membership, service, day, now):
        raise Conflict("slot_unavailable", "Это время недоступно. Обновите список окон.")

    extra = validate_extra(venue.category, extra)
    auto = membership.auto_confirm and client_no_show_count(client, now) < Setting.get("no_show_limit")
    respond_by = None if auto else min(now + timedelta(minutes=Setting.get("booking_response_minutes")), start)

    booking = Booking(
        client=client,
        client_name=client.name,
        client_phone=client.phone,
        membership=membership,
        specialist_id=membership.specialist_id,
        venue=venue,
        service=service,
        service_name=service.name,
        price=service.price,
        duration_minutes=service.duration_minutes,
        start=start,
        end=start + timedelta(minutes=service.duration_minutes),
        comment=comment or "",
        extra=extra,
        status=S.CONFIRMED if auto else S.PENDING,
        respond_by=respond_by,
    )
    with transaction.atomic():
        expire_stale(specialist_id=membership.specialist_id)
        _save_new(booking, client)
        params = _params(booking)
        notify(
            membership.specialist,
            N.BOOKING_NEW,
            data={"booking_id": booking.id},
            minutes=Setting.get("booking_response_minutes"),
            **params,
        )
        if auto:
            notify(client, N.BOOKING_CONFIRMED, data={"booking_id": booking.id}, **params)
    return booking


def create_manual_booking(actor, membership, start, service=None, duration_minutes=None, client_name="", client_phone="", comment=""):
    """Ручная запись или блокировка времени специалистом: сразу «Подтверждена»."""
    if membership.status != Membership.Status.ACCEPTED:
        raise ApiError("membership_inactive", "Специалист не принят в заведение.")
    if service is not None:
        if service.membership_id != membership.id:
            raise ApiError("service_unavailable", "Услуга недоступна.")
        duration_minutes = service.duration_minutes
    if not duration_minutes:
        raise ApiError("duration_required", "Укажите услугу или длительность.")
    is_block = service is None and not client_name and not client_phone
    booking = Booking(
        kind=Booking.Kind.BLOCK if is_block else Booking.Kind.BOOKING,
        source=Booking.Source.MANUAL,
        status=S.CONFIRMED,
        client_name=client_name,
        client_phone=client_phone,
        membership=membership,
        specialist_id=membership.specialist_id,
        venue=membership.venue,
        service=service,
        service_name=service.name if service else "",
        price=service.price if service else None,
        duration_minutes=duration_minutes,
        start=start,
        end=start + timedelta(minutes=duration_minutes),
        comment=comment,
    )
    with transaction.atomic():
        expire_stale(specialist_id=membership.specialist_id)
        _save_new(booking, actor)
    return booking


# --------------------------------------------------------------------------- статусы


def is_staff_of(user, booking):
    """Специалист записи или владелец заведения."""
    return user.id in (booking.specialist_id, booking.venue.owner_id)


def _transition(booking, new_status, actor, reason=""):
    old = booking.status
    booking.status = new_status
    booking.status_reason = reason or ""
    booking.save(update_fields=["status", "status_reason", "updated_at"])
    _log(booking, old, actor, reason)


def _locked(booking):
    return Booking.objects.select_for_update(of=("self",)).select_related("venue", "client", "specialist").get(pk=booking.pk)


def _expire_if_stale(booking, now):
    if booking.status == S.PENDING and booking.respond_by and booking.respond_by <= now:
        _transition(booking, S.EXPIRED, None)
        notify(booking.client, N.BOOKING_EXPIRED, data={"booking_id": booking.id}, **_params(booking))
        return True
    return False


def confirm(booking, actor):
    # Истечение сохраняется отдельно, чтобы не откатиться вместе с ошибкой ниже.
    expire_stale(specialist_id=booking.specialist_id)
    with transaction.atomic():
        booking = _locked(booking)
        if not is_staff_of(actor, booking):
            raise ApiError("forbidden", "Нет доступа к записи.", 403)
        if booking.status == S.EXPIRED:
            raise Conflict("booking_expired", "Заявка уже истекла.")
        if booking.status != S.PENDING:
            raise Conflict("invalid_status", "Заявку нельзя подтвердить в текущем статусе.")
        _transition(booking, S.CONFIRMED, actor)
        notify(booking.client, N.BOOKING_CONFIRMED, data={"booking_id": booking.id}, **_params(booking))
    return booking


def reject(booking, actor, reason=""):
    expire_stale(specialist_id=booking.specialist_id)
    with transaction.atomic():
        booking = _locked(booking)
        if not is_staff_of(actor, booking):
            raise ApiError("forbidden", "Нет доступа к записи.", 403)
        if booking.status == S.EXPIRED:
            raise Conflict("booking_expired", "Заявка уже истекла.")
        if booking.status != S.PENDING:
            raise Conflict("invalid_status", "Заявку нельзя отклонить в текущем статусе.")
        _transition(booking, S.REJECTED, actor, reason)
        notify(booking.client, N.BOOKING_REJECTED, data={"booking_id": booking.id}, **_params(booking))
    return booking


def cancel(booking, actor, reason=""):
    """Отмена: клиентом (своей записи) или специалистом/владельцем."""
    now = timezone.now()
    expire_stale(specialist_id=booking.specialist_id)
    with transaction.atomic():
        booking = _locked(booking)
        if booking.client_id == actor.id:
            if booking.status == S.EXPIRED:
                raise Conflict("booking_expired", "Заявка уже истекла.")
            if booking.status == S.CONFIRMED:
                min_hours = Setting.get("client_cancel_min_hours")
                if booking.start - now < timedelta(hours=min_hours):
                    raise Conflict("too_late", f"Отменить можно не позже чем за {min_hours} ч. Позвоните в заведение.")
            elif booking.status != S.PENDING:
                raise Conflict("invalid_status", "Запись нельзя отменить в текущем статусе.")
            _transition(booking, S.CANCELLED_CLIENT, actor, reason)
            notify(booking.specialist, N.BOOKING_CANCELLED, data={"booking_id": booking.id}, **_params(booking))
        elif is_staff_of(actor, booking):
            if booking.status != S.CONFIRMED:
                raise Conflict("invalid_status", "Отменить можно только подтверждённую запись; заявку — отклонить.")
            if booking.kind == Booking.Kind.BOOKING and not reason:
                raise ApiError("reason_required", "Укажите причину отмены.")
            _transition(booking, S.CANCELLED_SPECIALIST, actor, reason)
            if booking.client:
                notify(booking.client, N.BOOKING_CANCELLED, data={"booking_id": booking.id}, **_params(booking))
        else:
            raise ApiError("forbidden", "Нет доступа к записи.", 403)
    return booking


def mark_visit(booking, actor, status):
    """Итог визита: «Выполнена» или «Клиент не пришёл»."""
    assert status in (S.COMPLETED, S.NO_SHOW)
    with transaction.atomic():
        booking = _locked(booking)
        if not is_staff_of(actor, booking):
            raise ApiError("forbidden", "Нет доступа к записи.", 403)
        if booking.status != S.CONFIRMED or booking.kind != Booking.Kind.BOOKING:
            raise Conflict("invalid_status", "Итог можно поставить только подтверждённой записи.")
        if booking.start > timezone.now():
            raise Conflict("too_early", "Запись ещё не началась.")
        _transition(booking, status, actor)
    return booking


# --------------------------------------------------------------------------- фоновые задачи


def expire_stale(specialist_id=None, now=None):
    """Переводит просроченные заявки в «Истекла» и уведомляет клиентов."""
    now = now or timezone.now()
    qs = Booking.objects.filter(status=S.PENDING, respond_by__lte=now)
    if specialist_id:
        qs = qs.filter(specialist_id=specialist_id)
    count = 0
    with transaction.atomic():
        for booking in qs.select_for_update(skip_locked=True, of=("self",)).select_related("venue", "client"):
            _expire_if_stale(booking, now)
            count += 1
    return count


def run_periodic(now=None):
    """Раз в минуту: истечение заявок, напоминания, автозавершение."""
    now = now or timezone.now()
    stats = {"expired": expire_stale(now=now)}

    # Специалисту: до истечения заявки осталось 5 минут.
    expiring = Booking.objects.filter(
        status=S.PENDING, reminded_specialist=False, respond_by__gt=now, respond_by__lte=now + timedelta(minutes=5)
    ).select_related("venue", "client", "specialist")
    stats["specialist_reminders"] = 0
    for booking in expiring:
        notify(booking.specialist, N.BOOKING_EXPIRING, data={"booking_id": booking.id}, **_params(booking))
        Booking.objects.filter(pk=booking.pk).update(reminded_specialist=True)
        stats["specialist_reminders"] += 1

    # Клиенту: за 24 ч и за 2 ч до подтверждённой записи.
    stats["client_reminders"] = 0
    # Напоминание за 24 ч не нужно, если до записи уже меньше 2 ч — хватит второго.
    Booking.objects.filter(status=S.CONFIRMED, start__gt=now, start__lte=now + timedelta(hours=2)).update(reminded_24h=True)
    for flag, hours in (("reminded_24h", 24), ("reminded_2h", 2)):
        due = Booking.objects.filter(
            status=S.CONFIRMED, client__isnull=False, start__gt=now, start__lte=now + timedelta(hours=hours), **{flag: False}
        ).select_related("venue", "client")
        for booking in due:
            notify(booking.client, N.BOOKING_REMINDER, data={"booking_id": booking.id}, **_params(booking))
            Booking.objects.filter(pk=booking.pk).update(**{flag: True})
            stats["client_reminders"] += 1

    # Подтверждённые записи без итога через N часов после окончания — «Выполнена».
    cutoff = now - timedelta(hours=Setting.get("auto_complete_hours"))
    stats["auto_completed"] = 0
    with transaction.atomic():
        for booking in Booking.objects.select_for_update(skip_locked=True).filter(
            status=S.CONFIRMED, kind=Booking.Kind.BOOKING, end__lte=cutoff
        ):
            _transition(booking, S.COMPLETED, None, "auto")
            stats["auto_completed"] += 1
    return stats
