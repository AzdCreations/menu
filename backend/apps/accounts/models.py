import re
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone

PHONE_RE = re.compile(r"^\+998\d{9}$")


def normalize_phone(raw):
    """Приводит номер к виду +998XXXXXXXXX; возвращает None, если это не номер Узбекистана."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 9:
        digits = "998" + digits
    phone = "+" + digits
    return phone if PHONE_RE.match(phone) else None


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone, password=None, **extra):
        normalized = normalize_phone(phone)
        if not normalized:
            raise ValueError("Номер должен быть в формате +998XXXXXXXXX")
        user = self.model(phone=normalized, **extra)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(phone, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Status(models.TextChoices):
        ACTIVE = "active", "Активен"
        BLOCKED = "blocked", "Заблокирован"
        DELETED = "deleted", "Удалён"

    class Language(models.TextChoices):
        UZ = "uz", "O'zbekcha"
        RU = "ru", "Русский"

    phone = models.CharField(max_length=13, unique=True)
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True)
    name = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.UZ)
    is_specialist = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False, help_text="Главный админ (веб-панель).")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    block_reason = models.CharField(max_length=255, blank=True)
    pd_consent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name or '—'} ({self.phone})"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class Device(models.Model):
    class Platform(models.TextChoices):
        ANDROID = "android", "Android"
        IOS = "ios", "iOS"
        WEB = "web", "Web"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="devices")
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=10, choices=Platform.choices)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user_id} {self.platform}"


def new_login_token():
    return secrets.token_urlsafe(24)


def login_expiry():
    return timezone.now() + timezone.timedelta(minutes=settings.TELEGRAM_LOGIN_TTL_MINUTES)


class TelegramLogin(models.Model):
    """Одноразовый вход через Telegram-бота (раздел 3.1 ТЗ)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        CONFIRMED = "confirmed", "Подтверждён"
        USED = "used", "Использован"
        EXPIRED = "expired", "Истёк"

    token = models.CharField(max_length=64, unique=True, default=new_login_token)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    telegram_user_id = models.BigIntegerField(null=True, blank=True)
    phone = models.CharField(max_length=13, blank=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    expires_at = models.DateTimeField(default=login_expiry)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["telegram_user_id", "status"])]

    def __str__(self):
        return f"{self.token[:6]}… {self.status}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at
