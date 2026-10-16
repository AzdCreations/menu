from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        BOOKING_NEW = "booking_new", "Новая заявка"
        BOOKING_EXPIRING = "booking_expiring", "Заявка скоро истечёт"
        BOOKING_CONFIRMED = "booking_confirmed", "Запись подтверждена"
        BOOKING_REJECTED = "booking_rejected", "Запись отклонена"
        BOOKING_EXPIRED = "booking_expired", "Заявка истекла"
        BOOKING_CANCELLED = "booking_cancelled", "Запись отменена"
        BOOKING_REMINDER = "booking_reminder", "Напоминание о записи"
        JOIN_REQUEST = "join_request", "Заявка на вступление"
        JOIN_DECISION = "join_decision", "Решение по заявке"
        VENUE_DECISION = "venue_decision", "Решение модерации"
        ACCOUNT_BLOCKED = "account_blocked", "Блокировка"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=32, choices=Type.choices)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500)
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"])]
