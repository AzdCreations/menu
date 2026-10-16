from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.serializers import tokens_for
from apps.catalog.models import Category, Membership, Service, Venue, VenueHours, WorkingHours

TZ = ZoneInfo("Asia/Tashkent")


@pytest.fixture(autouse=True)
def _settings(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.TELEGRAM_BOT_TOKEN = ""
    settings.TELEGRAM_BOT_USERNAME = "test_bot"
    settings.TELEGRAM_WEBHOOK_SECRET = "secret"
    settings.DEV_LOGIN_ENABLED = True
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "DEFAULT_THROTTLE_RATES": {"telegram_start": "1000/hour"}}


def client_for(user=None):
    api = APIClient()
    if user is not None:
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_for(user)['access']}")
    return api


@pytest.fixture
def anon():
    return client_for()


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("+998900000000", "admin-pass-123", name="Admin")


@pytest.fixture
def category(db):
    return Category.objects.create(
        name_ru="Салоны", name_uz="Salonlar", specialist_name_ru="мастер", specialist_name_uz="usta"
    )


@pytest.fixture
def dental(db):
    return Category.objects.create(
        name_ru="Стоматологии", name_uz="Stomatologiya", specialist_name_ru="врач", specialist_name_uz="shifokor",
        booking_fields=[{"key": "reason", "label_ru": "Причина", "label_uz": "Sabab", "type": "select",
                         "options": ["Осмотр", "Боль"], "required": True}],
    )


@pytest.fixture
def owner(db):
    return User.objects.create_user("+998901111111", name="Owner", is_specialist=True)


@pytest.fixture
def client_user(db):
    return User.objects.create_user("+998902222222", name="Client")


@pytest.fixture
def other_client(db):
    return User.objects.create_user("+998903333333", name="Other")


def make_venue(owner, category, status=Venue.Status.APPROVED, **kwargs):
    venue = Venue.objects.create(
        category=category, owner=owner, name=kwargs.pop("name", "Salon"), address="Tashkent",
        lat=kwargs.pop("lat", "41.311081"), lng=kwargs.pop("lng", "69.279737"), status=status, **kwargs,
    )
    for day in range(7):
        VenueHours.objects.create(venue=venue, weekday=day, start=time(9), end=time(21), is_day_off=day == 6)
    return venue


@pytest.fixture
def venue(owner, category):
    return make_venue(owner, category)


@pytest.fixture
def membership(venue, owner):
    membership = Membership.objects.create(venue=venue, specialist=owner, status=Membership.Status.ACCEPTED, display_name="Master")
    for day in range(6):
        WorkingHours.objects.create(
            membership=membership, weekday=day, start=time(10), end=time(19), breaks=[{"start": "13:00", "end": "14:00"}]
        )
    return membership


@pytest.fixture
def service(membership):
    return Service.objects.create(membership=membership, name="Haircut", duration_minutes=60, price=100000)


@pytest.fixture
def monday():
    """Понедельник не раньше чем через 3 дня — чтобы «минимум до записи» не мешал."""
    day = date.today() + timedelta(days=3)
    return day + timedelta(days=(7 - day.weekday()) % 7)


def at(day, hour, minute=0):
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)
