import pytest
from django.utils import timezone

from apps.accounts.models import TelegramLogin, User

from .conftest import client_for

pytestmark = pytest.mark.django_db

WEBHOOK = "/api/v1/telegram/webhook"


def tg(api, message, secret="secret"):
    return api.post(WEBHOOK, {"message": message}, format="json", HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=secret)


def test_telegram_login_flow(anon):
    start = anon.post("/api/v1/auth/telegram/start")
    assert start.status_code == 201
    token = start.data["token"]
    assert start.data["bot_url"] == f"https://t.me/test_bot?start={token}"
    assert anon.get(f"/api/v1/auth/telegram/status/{token}").data == {"status": "pending"}

    sender = {"id": 777, "first_name": "Aziz", "last_name": "K"}
    assert tg(anon, {"from": sender, "chat": {"id": 777}, "text": f"/start {token}"}).status_code == 200
    tg(anon, {"from": sender, "chat": {"id": 777}, "contact": {"phone_number": "998 90 123 45 67", "user_id": 777}})

    status = anon.get(f"/api/v1/auth/telegram/status/{token}")
    assert status.data["status"] == "confirmed"
    assert status.data["user"]["phone"] == "+998901234567"
    assert status.data["user"]["name"] == "Aziz K"
    assert User.objects.get(phone="+998901234567").telegram_id == 777

    # Токен одноразовый.
    assert anon.get(f"/api/v1/auth/telegram/status/{token}").data == {"status": "used"}
    me = client_for(User.objects.get(phone="+998901234567")).get("/api/v1/me")
    assert me.status_code == 200


def test_foreign_contact_is_rejected(anon):
    token = anon.post("/api/v1/auth/telegram/start").data["token"]
    sender = {"id": 1}
    tg(anon, {"from": sender, "chat": {"id": 1}, "text": f"/start {token}"})
    tg(anon, {"from": sender, "chat": {"id": 1}, "contact": {"phone_number": "+998901234567", "user_id": 2}})
    assert anon.get(f"/api/v1/auth/telegram/status/{token}").data == {"status": "pending"}
    assert not User.objects.filter(phone="+998901234567").exists()


def test_non_uzbek_number_is_rejected(anon):
    token = anon.post("/api/v1/auth/telegram/start").data["token"]
    sender = {"id": 5}
    tg(anon, {"from": sender, "chat": {"id": 5}, "text": f"/start {token}"})
    tg(anon, {"from": sender, "chat": {"id": 5}, "contact": {"phone_number": "+79161234567", "user_id": 5}})
    assert anon.get(f"/api/v1/auth/telegram/status/{token}").data == {"status": "pending"}


def test_webhook_requires_secret(anon):
    assert tg(anon, {"from": {"id": 1}, "chat": {"id": 1}, "text": "/start x"}, secret="wrong").status_code == 403


def test_expired_login(anon):
    token = anon.post("/api/v1/auth/telegram/start").data["token"]
    TelegramLogin.objects.filter(token=token).update(expires_at=timezone.now())
    assert anon.get(f"/api/v1/auth/telegram/status/{token}").data == {"status": "expired"}


def test_blocked_user_cannot_login(anon, client_user):
    client_user.status = User.Status.BLOCKED
    client_user.save()
    token = anon.post("/api/v1/auth/telegram/start").data["token"]
    sender = {"id": 9}
    tg(anon, {"from": sender, "chat": {"id": 9}, "text": f"/start {token}"})
    tg(anon, {"from": sender, "chat": {"id": 9}, "contact": {"phone_number": client_user.phone, "user_id": 9}})
    assert anon.get(f"/api/v1/auth/telegram/status/{token}").data == {"status": "expired"}
    # И уже выданный токен перестаёт работать.
    assert client_for(client_user).get("/api/v1/me").status_code == 401


def test_dev_login_disabled(settings, anon):
    settings.DEV_LOGIN_ENABLED = False
    assert anon.post("/api/v1/auth/dev-login", {"phone": "+998901234567"}).status_code == 404


def test_admin_login(anon, admin_user, client_user):
    ok = anon.post("/api/v1/auth/admin-login", {"phone": admin_user.phone, "password": "admin-pass-123"})
    assert ok.status_code == 200 and ok.data["user"]["is_staff"]
    bad = anon.post("/api/v1/auth/admin-login", {"phone": admin_user.phone, "password": "nope"})
    assert bad.status_code == 401 and bad.data["code"] == "invalid_credentials"


def test_profile_update_and_delete(client_user):
    api = client_for(client_user)
    response = api.patch("/api/v1/me", {"name": "  Aziza ", "language": "ru", "pd_consent": True}, format="json")
    assert response.data["name"] == "Aziza" and response.data["pd_consent"] is True
    assert api.delete("/api/v1/me").status_code == 204
    client_user.refresh_from_db()
    assert client_user.status == User.Status.DELETED and client_user.phone.startswith("del")


def test_owner_cannot_delete_account(owner, venue):
    response = client_for(owner).delete("/api/v1/me")
    assert response.status_code == 409 and response.data["code"] == "owner_must_transfer"
