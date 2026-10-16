import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.services import available_slots, run_periodic
from apps.catalog.models import Membership, ScheduleException
from apps.core.models import Setting
from apps.notifications.models import Notification

from .conftest import at, client_for

pytestmark = pytest.mark.django_db


def book(user, membership, service, start, **extra):
    return client_for(user).post(
        "/api/v1/bookings",
        {"membership": membership.id, "service": service.id, "start": start.isoformat(), **extra},
        format="json",
    )


def slots(anon, membership, service, day):
    response = anon.get(f"/api/v1/specialists/{membership.id}/slots", {"service": service.id, "date": day.isoformat()})
    assert response.status_code == 200
    return response.data["slots"]


def test_slots_respect_schedule_break_and_step(anon, membership, service, monday):
    result = slots(anon, membership, service, monday)
    assert result[0] == at(monday, 10).isoformat()
    # Часовая услуга не пересекает перерыв 13:00–14:00 и заканчивается до 19:00.
    assert at(monday, 12).isoformat() in result
    assert at(monday, 12, 15).isoformat() not in result
    assert at(monday, 14).isoformat() in result
    assert result[-1] == at(monday, 18).isoformat()
    # Шаг 15 минут.
    assert at(monday, 10, 15).isoformat() in result


def test_no_slots_on_day_off_and_exceptions(anon, membership, service, monday):
    sunday = monday + timedelta(days=6)
    assert slots(anon, membership, service, sunday) == []
    ScheduleException.objects.create(membership=membership, date_from=monday, date_to=monday, kind="day_off")
    assert slots(anon, membership, service, monday) == []
    tuesday = monday + timedelta(days=1)
    ScheduleException.objects.create(
        membership=membership, date_from=tuesday, date_to=tuesday, kind="custom", start=at(tuesday, 15).time(), end=at(tuesday, 17).time()
    )
    assert slots(anon, membership, service, tuesday) == [at(tuesday, 15).isoformat(), at(tuesday, 15, 15).isoformat(), at(tuesday, 15, 30).isoformat(), at(tuesday, 15, 45).isoformat(), at(tuesday, 16).isoformat()]


def test_booking_flow_pending_confirm(anon, client_user, owner, membership, service, monday):
    response = book(client_user, membership, service, at(monday, 10), comment="first time")
    assert response.status_code == 201, response.data
    booking = Booking.objects.get(pk=response.data["id"])
    assert booking.status == Booking.Status.PENDING
    assert booking.respond_by <= timezone.now() + timedelta(minutes=10, seconds=5)
    assert Notification.objects.filter(user=owner, type=Notification.Type.BOOKING_NEW).exists()

    # Занятое время пропадает из окон.
    assert at(monday, 10).isoformat() not in slots(anon, membership, service, monday)
    assert at(monday, 10, 45).isoformat() not in slots(anon, membership, service, monday)

    # Клиент не может подтвердить свою заявку, специалист — может.
    assert client_for(client_user).post(f"/api/v1/bookings/{booking.id}/confirm").status_code == 403
    confirmed = client_for(owner).post(f"/api/v1/bookings/{booking.id}/confirm")
    assert confirmed.status_code == 200 and confirmed.data["status"] == "confirmed"
    assert confirmed.data["client_phone"] == client_user.phone
    assert Notification.objects.filter(user=client_user, type=Notification.Type.BOOKING_CONFIRMED).exists()
    assert list(booking.events.values_list("new_status", flat=True)) == ["pending", "confirmed"]


def test_slot_taken_returns_conflict(client_user, other_client, membership, service, monday):
    assert book(client_user, membership, service, at(monday, 11)).status_code == 201
    response = book(other_client, membership, service, at(monday, 11, 30))
    assert response.status_code == 409


def test_database_rejects_overlap_even_without_slot_check(client_user, membership, service, monday):
    """Exclusion constraint — последняя линия защиты от двойной записи."""
    from apps.bookings.services import create_manual_booking
    from apps.core.exceptions import Conflict

    create_manual_booking(membership.specialist, membership, at(monday, 15), service=service, client_name="A")
    with pytest.raises(Conflict):
        create_manual_booking(membership.specialist, membership, at(monday, 15, 30), service=service, client_name="B")


@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_only_one_wins(client_user, other_client, membership, service, monday):
    results = []

    def worker(user):
        try:
            results.append(book(user, membership, service, at(monday, 16)).status_code)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(user,)) for user in (client_user, other_client)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [201, 409]
    assert Booking.objects.filter(status=Booking.Status.PENDING).count() == 1


def test_pending_expires_after_response_window(anon, client_user, membership, service, monday):
    booking_id = book(client_user, membership, service, at(monday, 10)).data["id"]
    Booking.objects.filter(pk=booking_id).update(respond_by=timezone.now() - timedelta(seconds=1))
    # Просроченная заявка больше не занимает время...
    assert at(monday, 10).isoformat() in slots(anon, membership, service, monday)
    # ...и подтвердить её нельзя.
    response = client_for(membership.specialist).post(f"/api/v1/bookings/{booking_id}/confirm")
    assert response.status_code == 409 and response.data["code"] == "booking_expired"
    assert Booking.objects.get(pk=booking_id).status == Booking.Status.EXPIRED
    assert Notification.objects.filter(user=client_user, type=Notification.Type.BOOKING_EXPIRED).exists()


def test_expired_slot_can_be_booked_again(client_user, other_client, membership, service, monday):
    booking_id = book(client_user, membership, service, at(monday, 10)).data["id"]
    Booking.objects.filter(pk=booking_id).update(respond_by=timezone.now() - timedelta(seconds=1))
    assert book(other_client, membership, service, at(monday, 10)).status_code == 201


def test_auto_confirm(client_user, membership, service, monday):
    membership.auto_confirm = True
    membership.save()
    response = book(client_user, membership, service, at(monday, 10))
    assert response.data["status"] == "confirmed"


def test_client_cancel_rules(client_user, membership, service, monday):
    api = client_for(client_user)
    booking_id = book(client_user, membership, service, at(monday, 10)).data["id"]
    assert api.post(f"/api/v1/bookings/{booking_id}/cancel").data["status"] == "cancelled_client"

    booking_id = book(client_user, membership, service, at(monday, 12)).data["id"]
    client_for(membership.specialist).post(f"/api/v1/bookings/{booking_id}/confirm")
    # Подтверждённую запись меньше чем за 2 ч отменить нельзя.
    Booking.objects.filter(pk=booking_id).update(start=timezone.now() + timedelta(hours=1), end=timezone.now() + timedelta(hours=2))
    response = api.post(f"/api/v1/bookings/{booking_id}/cancel")
    assert response.status_code == 409 and response.data["code"] == "too_late"


def test_specialist_cancel_needs_reason(client_user, owner, membership, service, monday):
    booking_id = book(client_user, membership, service, at(monday, 10)).data["id"]
    api = client_for(owner)
    api.post(f"/api/v1/bookings/{booking_id}/confirm")
    assert api.post(f"/api/v1/bookings/{booking_id}/cancel").data["code"] == "reason_required"
    response = api.post(f"/api/v1/bookings/{booking_id}/cancel", {"reason": "Заболела"})
    assert response.data["status"] == "cancelled_specialist"
    assert Notification.objects.filter(user=client_user, type=Notification.Type.BOOKING_CANCELLED).exists()


def test_pending_limit_per_client(client_user, membership, service, monday):
    for hour in (10, 11, 12):
        assert book(client_user, membership, service, at(monday, hour)).status_code == 201
    response = book(client_user, membership, service, at(monday, 15))
    assert response.status_code == 400 and response.data["code"] == "too_many_pending"


def test_required_booking_fields(client_user, owner, dental, monday):
    from .conftest import make_venue

    other_owner = type(owner).objects.create_user("+998905555555", name="Doc")
    venue = make_venue(other_owner, dental, name="Dent")
    membership = Membership.objects.create(venue=venue, specialist=other_owner, status="accepted")
    membership.working_hours.create(weekday=0, start=at(monday, 10).time(), end=at(monday, 18).time())
    service = membership.services.create(name="Осмотр", duration_minutes=30)
    response = book(client_user, membership, service, at(monday, 10))
    assert response.data["code"] == "extra_required"
    response = book(client_user, membership, service, at(monday, 10), extra={"reason": "Боль"})
    assert response.status_code == 201 and response.data["extra"] == {"reason": "Боль"}


def test_manual_booking_and_block(owner, membership, service, monday, anon):
    api = client_for(owner)
    manual = api.post(
        "/api/v1/pro/bookings/manual",
        {"start": at(monday, 10).isoformat(), "service": service.id, "client_name": "Звонок", "client_phone": "+998901112233"},
        format="json",
    )
    assert manual.status_code == 201 and manual.data["status"] == "confirmed" and manual.data["source"] == "manual"
    block = api.post(
        "/api/v1/pro/blocks", {"start": at(monday, 15).isoformat(), "end": at(monday, 16).isoformat()}, format="json"
    )
    assert block.status_code == 201 and block.data["kind"] == "block"
    free = slots(anon, membership, service, monday)
    assert at(monday, 10).isoformat() not in free and at(monday, 15).isoformat() not in free

    calendar = api.get("/api/v1/pro/bookings", {"from": monday.isoformat(), "to": monday.isoformat()})
    assert [item["kind"] for item in calendar.data] == ["booking", "block"]


def test_complete_and_no_show(client_user, owner, membership, service, monday):
    booking_id = book(client_user, membership, service, at(monday, 10)).data["id"]
    api = client_for(owner)
    api.post(f"/api/v1/bookings/{booking_id}/confirm")
    assert api.post(f"/api/v1/bookings/{booking_id}/complete").data["code"] == "too_early"
    Booking.objects.filter(pk=booking_id).update(start=timezone.now() - timedelta(hours=1), end=timezone.now())
    assert api.post(f"/api/v1/bookings/{booking_id}/no-show").data["status"] == "no_show"


def test_other_specialist_cannot_see_booking(client_user, other_client, membership, service, monday):
    booking_id = book(client_user, membership, service, at(monday, 10)).data["id"]
    assert client_for(other_client).get(f"/api/v1/bookings/{booking_id}").status_code == 403


def test_my_bookings(client_user, membership, service, monday):
    book(client_user, membership, service, at(monday, 10))
    response = client_for(client_user).get("/api/v1/bookings/my", {"scope": "upcoming"})
    assert response.data["count"] == 1 and response.data["results"][0]["venue_name"] == "Salon"


def test_periodic_jobs(client_user, owner, membership, service, monday):
    pending_id = book(client_user, membership, service, at(monday, 10)).data["id"]
    Booking.objects.filter(pk=pending_id).update(respond_by=timezone.now() + timedelta(minutes=3))
    stats = run_periodic()
    assert stats["specialist_reminders"] == 1
    assert run_periodic()["specialist_reminders"] == 0  # не повторяется

    Booking.objects.filter(pk=pending_id).update(respond_by=timezone.now() - timedelta(minutes=1))
    assert run_periodic()["expired"] == 1

    confirmed_id = book(client_user, membership, service, at(monday, 12)).data["id"]
    client_for(owner).post(f"/api/v1/bookings/{confirmed_id}/confirm")
    Booking.objects.filter(pk=confirmed_id).update(start=timezone.now() + timedelta(hours=1), end=timezone.now() + timedelta(hours=2))
    assert run_periodic()["client_reminders"] == 1  # только «за 2 часа», без дубля «за 24 часа»
    Booking.objects.filter(pk=confirmed_id).update(start=timezone.now() - timedelta(hours=27), end=timezone.now() - timedelta(hours=26))
    assert run_periodic()["auto_completed"] == 1
    assert Booking.objects.get(pk=confirmed_id).status == Booking.Status.COMPLETED


def test_response_window_setting(client_user, membership, service, monday):
    Setting.objects.create(key="booking_response_minutes", value=30)
    booking = Booking.objects.get(pk=book(client_user, membership, service, at(monday, 10)).data["id"])
    assert booking.respond_by > timezone.now() + timedelta(minutes=29)


def test_slots_for_past_or_far_dates_are_empty(membership, service):
    today = timezone.localdate()
    assert available_slots(membership, service, today - timedelta(days=1)) == []
    assert available_slots(membership, service, today + timedelta(days=60)) == []
