import pytest

from apps.accounts.models import User
from apps.catalog.models import Membership, Venue
from apps.core.models import AuditLog
from apps.notifications.models import Notification

from .conftest import at, client_for

pytestmark = pytest.mark.django_db

VENUE = {
    "name": "Barber One",
    "address": "Tashkent, Chilonzor 1",
    "lat": "41.285000",
    "lng": "69.204000",
    "phone": "+998901234567",
    "hours": [{"weekday": d, "start": "09:00", "end": "20:00", "is_day_off": False} for d in range(6)]
    + [{"weekday": 6, "is_day_off": True}],
}


def test_create_venue_moderation_and_visibility(anon, admin_user, category, monday):
    founder = User.objects.create_user("+998907777777", name="Founder")
    api = client_for(founder)
    created = api.post("/api/v1/pro/venues", {**VENUE, "category": category.id}, format="json")
    assert created.status_code == 201, created.data
    venue_id = created.data["id"]
    assert created.data["status"] == "pending" and created.data["is_owner"]
    founder.refresh_from_db()
    assert founder.is_specialist

    # Пока на модерации — клиентам не видно.
    assert anon.get(f"/api/v1/venues/{venue_id}").status_code == 404

    # Специалист настраивает услуги и график.
    service = api.post("/api/v1/pro/services", {"name": "Fade", "duration_minutes": 45, "price": 80000}, format="json")
    assert service.status_code == 201
    hours = api.put(
        "/api/v1/pro/working-hours",
        [{"weekday": d, "start": "10:00", "end": "18:00", "breaks": []} for d in range(5)],
        format="json",
    )
    assert hours.status_code == 200 and len(hours.data) == 5

    admin = client_for(admin_user)
    queue = admin.get("/api/v1/admin/venues", {"status": "pending"})
    assert [v["id"] for v in queue.data["results"]] == [venue_id]
    assert admin.post(f"/api/v1/admin/venues/{venue_id}/reject").data["code"] == "reason_required"
    approved = admin.post(f"/api/v1/admin/venues/{venue_id}/approve")
    assert approved.status_code == 200 and approved.data["status"] == "approved" and approved.data["free_until"]
    assert Notification.objects.filter(user=founder, type=Notification.Type.VENUE_DECISION).exists()
    assert AuditLog.objects.filter(action="venue.approve", object_id=str(venue_id)).exists()

    detail = anon.get(f"/api/v1/venues/{venue_id}")
    assert detail.status_code == 200
    assert [s["name"] for s in detail.data["specialists"]] == ["Founder"]
    assert detail.data["specialists"][0]["services"][0]["name"] == "Fade"

    listing = anon.get("/api/v1/venues", {"category": category.id, "lat": "41.2851", "lng": "69.2041"})
    assert listing.data[0]["id"] == venue_id and listing.data[0]["distance_km"] < 0.1


def test_duplicate_venue_is_flagged(owner, venue, category):
    other = User.objects.create_user("+998906666666", name="X")
    response = client_for(other).post(
        "/api/v1/pro/venues",
        {**VENUE, "category": category.id, "name": "salon", "lat": "41.311200", "lng": "69.279800"},
        format="json",
    )
    assert response.status_code == 201
    assert response.data["duplicates"][0]["id"] == venue.id
    assert Venue.objects.get(pk=response.data["id"]).possible_duplicate_id == venue.id


def test_rejected_venue_resubmits_on_edit(admin_user, category):
    founder = User.objects.create_user("+998907777777", name="Founder")
    venue_id = client_for(founder).post("/api/v1/pro/venues", {**VENUE, "category": category.id}, format="json").data["id"]
    client_for(admin_user).post(f"/api/v1/admin/venues/{venue_id}/reject", {"reason": "Нет фото"})
    edited = client_for(founder).patch(f"/api/v1/pro/venues/{venue_id}", {"address": "New address"}, format="json")
    assert edited.data["status"] == "pending" and edited.data["decision_reason"] == ""


def test_join_venue_flow(owner, venue, membership, service, client_user, anon):
    specialist = User.objects.create_user("+998908888888", name="Newbie")
    api = client_for(specialist)
    joined = api.post(f"/api/v1/pro/venues/{venue.id}/join")
    assert joined.status_code == 201 and joined.data["status"] == "pending"
    assert Notification.objects.filter(user=owner, type=Notification.Type.JOIN_REQUEST).exists()
    assert api.post(f"/api/v1/pro/venues/{venue.id}/join").status_code == 409

    # Чужой специалист не может принять заявку.
    assert api.post(f"/api/v1/pro/members/{joined.data['id']}/approve").status_code == 403
    owner_api = client_for(owner)
    assert owner_api.post(f"/api/v1/pro/members/{joined.data['id']}/approve").data["status"] == "accepted"

    # Без услуг и графика специалист клиентам не виден.
    names = [s["name"] for s in anon.get(f"/api/v1/venues/{venue.id}").data["specialists"]]
    assert names == ["Master"]

    members = owner_api.get(f"/api/v1/pro/venues/{venue.id}/members")
    assert {m["name"] for m in members.data} == {"Master", "Newbie"}

    # Владелец не может выйти, обычный специалист — может.
    assert owner_api.post("/api/v1/pro/membership/leave").data["code"] == "owner_cannot_leave"
    assert api.post("/api/v1/pro/membership/leave").status_code == 204
    assert Membership.objects.get(pk=joined.data["id"]).status == "left"


def test_transfer_owner(owner, venue, membership):
    specialist = User.objects.create_user("+998908888888", name="Next")
    member = Membership.objects.create(venue=venue, specialist=specialist, status="accepted")
    response = client_for(owner).post(f"/api/v1/pro/venues/{venue.id}/transfer-owner", {"membership_id": member.id})
    assert response.status_code == 200
    venue.refresh_from_db()
    assert venue.owner_id == specialist.id


def test_block_venue_cancels_future_bookings(admin_user, client_user, owner, membership, service, monday):
    booking = client_for(client_user).post(
        "/api/v1/bookings", {"membership": membership.id, "service": service.id, "start": at(monday, 10).isoformat()}, format="json"
    ).data
    client_for(owner).post(f"/api/v1/bookings/{booking['id']}/confirm")
    admin = client_for(admin_user)
    response = admin.post(f"/api/v1/admin/venues/{membership.venue_id}/block", {"reason": "Жалобы"})
    assert response.data["status"] == "blocked"
    assert client_for(client_user).get(f"/api/v1/bookings/{booking['id']}").data["status"] == "cancelled_specialist"


def test_admin_blocks_user(admin_user, client_user):
    admin = client_for(admin_user)
    response = admin.post(f"/api/v1/admin/users/{client_user.id}/block", {"reason": "Спам"})
    assert response.data["status"] == "blocked"
    assert client_for(client_user).get("/api/v1/me").status_code == 401
    assert admin.post(f"/api/v1/admin/users/{client_user.id}/unblock").data["status"] == "active"


def test_admin_endpoints_require_staff(client_user):
    assert client_for(client_user).get("/api/v1/admin/venues").status_code == 403


def test_admin_categories_and_settings(admin_user, anon):
    admin = client_for(admin_user)
    created = admin.post(
        "/api/v1/admin/categories/",
        {"name_ru": "Массаж", "name_uz": "Massaj", "specialist_name_ru": "массажист", "specialist_name_uz": "massajchi",
         "booking_fields": [{"key": "zone", "type": "select", "options": []}]},
        format="json",
    )
    assert created.status_code == 400  # у select нет вариантов
    created = admin.post(
        "/api/v1/admin/categories/",
        {"name_ru": "Массаж", "name_uz": "Massaj", "specialist_name_ru": "массажист", "specialist_name_uz": "massajchi"},
        format="json",
    )
    assert created.status_code == 201
    assert [c["name"] for c in anon.get("/api/v1/categories", HTTP_ACCEPT_LANGUAGE="uz").data] == ["Massaj"]
    admin.patch(f"/api/v1/admin/categories/{created.data['id']}/", {"is_active": False}, format="json")
    assert anon.get("/api/v1/categories").data == []

    settings = admin.patch("/api/v1/admin/settings", {"booking_response_minutes": 15}, format="json")
    assert settings.data["booking_response_minutes"] == 15
    assert admin.patch("/api/v1/admin/settings", {"booking_response_minutes": "x"}, format="json").status_code == 400
    assert admin.get("/api/v1/admin/stats").status_code == 200
    assert admin.get("/api/v1/admin/audit-log").data["count"] >= 2
