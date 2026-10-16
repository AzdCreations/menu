import math
from difflib import SequenceMatcher

from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from apps.core.exceptions import ApiError, Conflict
from apps.core.models import Setting
from apps.notifications.models import Notification
from apps.notifications.services import notify, word

from .models import Membership, Service, Venue, VenueHours

DUPLICATE_RADIUS_M = 100


def distance_km(lat1, lng1, lat2, lng2):
    lat1, lng1, lat2, lng2 = map(math.radians, map(float, (lat1, lng1, lat2, lng2)))
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def bbox(lat, lng, radius_km):
    dlat = radius_km / 111.0
    dlng = radius_km / (111.0 * max(math.cos(math.radians(float(lat))), 0.01))
    return {
        "lat__gte": float(lat) - dlat,
        "lat__lte": float(lat) + dlat,
        "lng__gte": float(lng) - dlng,
        "lng__lte": float(lng) + dlng,
    }


def similar_names(a, b):
    a, b = a.strip().lower(), b.strip().lower()
    return a in b or b in a or SequenceMatcher(None, a, b).ratio() >= 0.8


def find_duplicates(name, lat, lng, exclude_id=None):
    radius_km = DUPLICATE_RADIUS_M / 1000
    candidates = Venue.objects.filter(**bbox(lat, lng, radius_km)).exclude(status__in=[Venue.Status.REJECTED, Venue.Status.CLOSED])
    if exclude_id:
        candidates = candidates.exclude(pk=exclude_id)
    return [
        venue for venue in candidates
        if distance_km(lat, lng, venue.lat, venue.lng) <= radius_km and similar_names(name, venue.name)
    ]


def visible_memberships(venue_ids=None):
    """Специалисты, видимые клиентам: принят, заведение одобрено, есть услуга и график."""
    qs = (
        Membership.objects.filter(
            status=Membership.Status.ACCEPTED, venue__status=Venue.Status.APPROVED, specialist__status="active"
        )
        .annotate(
            active_services=Count("services", filter=Q(services__is_active=True), distinct=True),
            hours_count=Count("working_hours", distinct=True),
        )
        .filter(active_services__gt=0, hours_count__gt=0)
        .select_related("specialist", "venue")
        .prefetch_related(Prefetch("services", queryset=Service.objects.filter(is_active=True)))
    )
    if venue_ids is not None:
        qs = qs.filter(venue_id__in=venue_ids)
    return qs


def active_membership(user):
    return (
        Membership.objects.filter(specialist=user, status__in=Membership.ACTIVE_STATUSES)
        .select_related("venue", "specialist")
        .first()
    )


def save_venue_hours(venue, hours):
    VenueHours.objects.filter(venue=venue).delete()
    VenueHours.objects.bulk_create(VenueHours(venue=venue, **item) for item in hours)


def create_venue(owner, data):
    if active_membership(owner):
        raise Conflict("already_member", "Вы уже состоите в заведении. Сначала выйдите из него.")
    limit = Setting.get("max_venues_per_owner")
    owned = Venue.objects.filter(owner=owner).exclude(status__in=[Venue.Status.REJECTED, Venue.Status.CLOSED]).count()
    if owned >= limit:
        raise ApiError("venue_limit", f"Можно создать не больше {limit} заведений.")

    hours = data.pop("hours", [])
    duplicates = find_duplicates(data["name"], data["lat"], data["lng"])
    with transaction.atomic():
        venue = Venue.objects.create(owner=owner, possible_duplicate=duplicates[0] if duplicates else None, **data)
        save_venue_hours(venue, hours)
        Membership.objects.create(
            venue=venue, specialist=owner, status=Membership.Status.ACCEPTED, display_name=owner.name
        )
        if not owner.is_specialist:
            owner.is_specialist = True
            owner.save(update_fields=["is_specialist", "updated_at"])
    return venue, duplicates


def join_venue(user, venue):
    if venue.status != Venue.Status.APPROVED:
        raise ApiError("venue_unavailable", "Заведение недоступно.")
    if active_membership(user):
        raise Conflict("already_member", "Вы уже состоите в заведении или подали заявку.")
    try:
        with transaction.atomic():
            membership = Membership.objects.create(venue=venue, specialist=user, display_name=user.name)
    except IntegrityError as exc:
        raise Conflict("already_member", "Вы уже состоите в заведении или подали заявку.") from exc
    if not user.is_specialist:
        user.is_specialist = True
        user.save(update_fields=["is_specialist", "updated_at"])
    notify(venue.owner, Notification.Type.JOIN_REQUEST, data={"membership_id": membership.id}, name=user.name or user.phone, venue=venue.name)
    return membership


def decide_membership(membership, accept):
    if membership.status != Membership.Status.PENDING:
        raise Conflict("invalid_status", "Заявка уже рассмотрена.")
    membership.status = Membership.Status.ACCEPTED if accept else Membership.Status.REJECTED
    membership.save(update_fields=["status", "updated_at"])
    notify(
        membership.specialist,
        Notification.Type.JOIN_DECISION,
        data={"membership_id": membership.id},
        venue=membership.venue.name,
        decision=lambda lang: word("accepted" if accept else "rejected", lang),
    )
    return membership


def end_membership(membership, status, actor):
    """Выход или исключение: будущие записи отменяются с уведомлением клиентов."""
    from apps.bookings.models import Booking
    from apps.bookings.services import cancel, expire_stale, reject

    if membership.is_owner:
        raise Conflict("owner_cannot_leave", "Владелец не может выйти: сначала передайте права владельца.")
    if membership.status not in Membership.ACTIVE_STATUSES:
        raise Conflict("invalid_status", "Специалист уже не состоит в заведении.")
    reason = "Специалист больше не работает в заведении"
    owner = membership.venue.owner
    expire_stale(specialist_id=membership.specialist_id)
    for booking in Booking.objects.filter(membership=membership, status=Booking.Status.PENDING):
        reject(booking, owner, reason)
    for booking in Booking.objects.filter(membership=membership, status=Booking.Status.CONFIRMED, start__gt=timezone.now()):
        cancel(booking, owner, reason)
    membership.status = status
    membership.save(update_fields=["status", "updated_at"])
    return membership


def transfer_owner(venue, target):
    if target.venue_id != venue.id or target.status != Membership.Status.ACCEPTED:
        raise ApiError("invalid_member", "Права можно передать только принятому специалисту этого заведения.")
    venue.owner = target.specialist
    venue.save(update_fields=["owner", "updated_at"])
    return venue
