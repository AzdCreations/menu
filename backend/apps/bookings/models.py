from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import RangeOperators
from django.db import models
from django.db.models import F, Func, Q


class TsTzRange(Func):
    function = "TSTZRANGE"
    output_field = models.DateTimeField()


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает подтверждения"
        CONFIRMED = "confirmed", "Подтверждена"
        REJECTED = "rejected", "Отклонена"
        EXPIRED = "expired", "Истекла"
        CANCELLED_CLIENT = "cancelled_client", "Отменена клиентом"
        CANCELLED_SPECIALIST = "cancelled_specialist", "Отменена специалистом"
        COMPLETED = "completed", "Выполнена"
        NO_SHOW = "no_show", "Клиент не пришёл"

    # Статусы, которые занимают время специалиста.
    BUSY_STATUSES = (Status.PENDING, Status.CONFIRMED)

    class Kind(models.TextChoices):
        BOOKING = "booking", "Запись"
        BLOCK = "block", "Блокировка времени"

    class Source(models.TextChoices):
        APP = "app", "Приложение"
        MANUAL = "manual", "Вручную"

    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.BOOKING)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.APP)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)

    client = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="bookings")
    client_name = models.CharField(max_length=100, blank=True)
    client_phone = models.CharField(max_length=20, blank=True)

    membership = models.ForeignKey("catalog.Membership", on_delete=models.PROTECT, related_name="bookings")
    # Дублирует membership.specialist: по нему база запрещает пересечения времени.
    specialist = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="specialist_bookings")
    venue = models.ForeignKey("catalog.Venue", on_delete=models.PROTECT, related_name="bookings")
    service = models.ForeignKey("catalog.Service", null=True, blank=True, on_delete=models.SET_NULL, related_name="bookings")
    service_name = models.CharField(max_length=120, blank=True)
    price = models.PositiveIntegerField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField()

    start = models.DateTimeField()
    end = models.DateTimeField()

    comment = models.CharField(max_length=500, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    status_reason = models.CharField(max_length=500, blank=True)
    respond_by = models.DateTimeField(null=True, blank=True)

    reminded_24h = models.BooleanField(default=False)
    reminded_2h = models.BooleanField(default=False)
    reminded_specialist = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start"]
        indexes = [
            models.Index(fields=["specialist", "start"]),
            models.Index(fields=["client", "start"]),
            models.Index(fields=["status", "respond_by"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(end__gt=F("start")), name="booking_end_after_start"),
            # Защита от двойной записи на уровне базы (раздел 5.4 ТЗ).
            ExclusionConstraint(
                name="booking_no_overlap_per_specialist",
                expressions=[
                    (TsTzRange("start", "end"), RangeOperators.OVERLAPS),
                    ("specialist", RangeOperators.EQUAL),
                ],
                condition=Q(status__in=["pending", "confirmed"]),
            ),
        ]

    def __str__(self):
        return f"#{self.pk} {self.start:%Y-%m-%d %H:%M} {self.status}"

    @property
    def is_busy(self):
        return self.status in self.BUSY_STATUSES


class BookingEvent(models.Model):
    """История смены статусов записи: кто, когда, почему."""

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="events")
    old_status = models.CharField(max_length=24, blank=True)
    new_status = models.CharField(max_length=24)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reason = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
