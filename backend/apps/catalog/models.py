from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import translation


class Category(models.Model):
    """Направление бронирования: салон, стоматология и т. д."""

    name_uz = models.CharField(max_length=100)
    name_ru = models.CharField(max_length=100)
    specialist_name_uz = models.CharField(max_length=50, help_text="Например, «usta», «shifokor».")
    specialist_name_ru = models.CharField(max_length=50, help_text="Например, «мастер», «врач».")
    icon = models.CharField(max_length=50, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    # Доп. поля анкеты записи: [{"key", "label_uz", "label_ru", "type": text|select|bool,
    #                            "options": [...], "required": bool}]
    booking_fields = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name_ru

    @property
    def name(self):
        return self.name_uz if translation.get_language() == "uz" else self.name_ru

    @property
    def specialist_name(self):
        return self.specialist_name_uz if translation.get_language() == "uz" else self.specialist_name_ru


class Venue(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "На модерации"
        APPROVED = "approved", "Одобрено"
        REJECTED = "rejected", "Отклонено"
        BLOCKED = "blocked", "Заблокировано"
        CLOSED = "closed", "Закрыто"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="venues")
    name = models.CharField(max_length=120)
    address = models.CharField(max_length=255)
    lat = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    lng = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    phone = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=40, default="Asia/Tashkent")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="owned_venues")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    decision_reason = models.CharField(max_length=500, blank=True)
    possible_duplicate = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    free_until = models.DateField(null=True, blank=True, help_text="Конец бесплатного периода (подписка, вне MVP).")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "category"])]

    def __str__(self):
        return self.name


class VenuePhoto(models.Model):
    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="venues/%Y/%m/")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class VenueHours(models.Model):
    """График работы заведения по дням недели (0 — понедельник)."""

    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name="hours")
    weekday = models.PositiveSmallIntegerField(validators=[MaxValueValidator(6)])
    start = models.TimeField(null=True, blank=True)
    end = models.TimeField(null=True, blank=True)
    is_day_off = models.BooleanField(default=False)

    class Meta:
        ordering = ["weekday"]
        constraints = [models.UniqueConstraint(fields=["venue", "weekday"], name="venue_hours_unique_day")]


class Membership(models.Model):
    """Специалист в заведении. Услуги и график привязаны к членству."""

    class Status(models.TextChoices):
        PENDING = "pending", "Заявка"
        ACCEPTED = "accepted", "Принят"
        REJECTED = "rejected", "Отклонён"
        LEFT = "left", "Вышел"
        REMOVED = "removed", "Исключён"

    ACTIVE_STATUSES = (Status.PENDING, Status.ACCEPTED)

    venue = models.ForeignKey(Venue, on_delete=models.CASCADE, related_name="memberships")
    specialist = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    display_name = models.CharField(max_length=100, blank=True)
    photo = models.ImageField(upload_to="specialists/%Y/%m/", null=True, blank=True)
    bio = models.CharField(max_length=500, blank=True)
    auto_confirm = models.BooleanField(default=False)
    # Параметры расчёта окон (раздел 5.1).
    slot_step_minutes = models.PositiveSmallIntegerField(default=15, validators=[MinValueValidator(5), MaxValueValidator(120)])
    min_lead_minutes = models.PositiveIntegerField(default=60, validators=[MaxValueValidator(7 * 24 * 60)])
    horizon_days = models.PositiveSmallIntegerField(default=30, validators=[MinValueValidator(1), MaxValueValidator(180)])
    buffer_minutes = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(120)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            # В первой версии специалист работает только в одном заведении.
            models.UniqueConstraint(
                fields=["specialist"],
                condition=Q(status__in=["pending", "accepted"]),
                name="membership_one_active_per_specialist",
            ),
        ]

    def __str__(self):
        return f"{self.public_name} @ {self.venue_id}"

    @property
    def public_name(self):
        return self.display_name or self.specialist.name

    @property
    def is_owner(self):
        return self.venue.owner_id == self.specialist_id


class Service(models.Model):
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="services")
    name = models.CharField(max_length=120)
    duration_minutes = models.PositiveSmallIntegerField(validators=[MinValueValidator(5), MaxValueValidator(12 * 60)])
    price = models.PositiveIntegerField(null=True, blank=True, help_text="Сум; пусто — цена не показывается.")
    price_from = models.BooleanField(default=False, help_text="Показывать как «от …».")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class WorkingHours(models.Model):
    """Недельный график специалиста; breaks: [{"start": "13:00", "end": "14:00"}]."""

    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="working_hours")
    weekday = models.PositiveSmallIntegerField(validators=[MaxValueValidator(6)])
    start = models.TimeField()
    end = models.TimeField()
    breaks = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["weekday"]
        constraints = [models.UniqueConstraint(fields=["membership", "weekday"], name="working_hours_unique_day")]


class ScheduleException(models.Model):
    class Kind(models.TextChoices):
        DAY_OFF = "day_off", "Выходной"
        CUSTOM = "custom", "Другое время"

    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="exceptions")
    date_from = models.DateField()
    date_to = models.DateField()
    kind = models.CharField(max_length=10, choices=Kind.choices)
    start = models.TimeField(null=True, blank=True)
    end = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["date_from"]
