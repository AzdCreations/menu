from django.conf import settings
from django.db import models

# Значения по умолчанию для настроек, которые админ меняет в веб-панели.
SETTING_DEFAULTS = {
    # Сколько минут специалист может ответить на заявку (раздел 5.1).
    "booking_response_minutes": 10,
    # До скольки часов до начала клиент может отменить подтверждённую запись.
    "client_cancel_min_hours": 2,
    # Сколько заявок «Ожидает подтверждения» может быть у клиента одновременно.
    "max_pending_per_client": 3,
    # Неявок за 90 дней, после которых автоподтверждение для клиента выключается.
    "no_show_limit": 3,
    # Сколько заведений может создать один аккаунт.
    "max_venues_per_owner": 2,
    # Оплата взноса за заведение (в MVP выключена).
    "payment_enabled": False,
    "entry_fee": 5000,
    # Бесплатный период после одобрения заведения, в месяцах.
    "free_period_months": 6,
    # Через сколько часов после окончания записи она автоматически «Выполнена».
    "auto_complete_hours": 24,
}


class Setting(models.Model):
    key = models.CharField(max_length=64, unique=True)
    value = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key}={self.value}"

    @classmethod
    def get(cls, key):
        if key not in SETTING_DEFAULTS:
            raise KeyError(key)
        row = cls.objects.filter(key=key).first()
        return row.value if row else SETTING_DEFAULTS[key]

    @classmethod
    def all_values(cls):
        values = dict(SETTING_DEFAULTS)
        values.update({row.key: row.value for row in cls.objects.filter(key__in=SETTING_DEFAULTS)})
        return values


class AuditLog(models.Model):
    """Журнал действий админа (только запись, без изменения)."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=64)
    object_type = models.CharField(max_length=64)
    object_id = models.CharField(max_length=64)
    data = models.JSONField(default=dict, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action} {self.object_type}#{self.object_id}"


def audit(request, action, obj, **data):
    ip = request.META.get("REMOTE_ADDR") if request else None
    return AuditLog.objects.create(
        actor=request.user if request and request.user.is_authenticated else None,
        action=action,
        object_type=obj.__class__.__name__,
        object_id=str(obj.pk),
        data=data,
        ip=ip,
    )
