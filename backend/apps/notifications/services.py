"""Уведомления: запись в базу + пуш на устройства пользователя.

Тексты на языке получателя. Пуш отправляется через PUSH_BACKEND:
"log" — только пишет в лог (разработка), "fcm" — Firebase Cloud Messaging.
"""

import logging

from django.conf import settings
from django.db import transaction

from .models import Notification

logger = logging.getLogger(__name__)

T = Notification.Type

TEMPLATES = {
    T.BOOKING_NEW: {
        "ru": ("Новая заявка", "{client} — {service}, {when}. Ответьте в течение {minutes} мин."),
        "uz": ("Yangi buyurtma", "{client} — {service}, {when}. {minutes} daqiqa ichida javob bering."),
    },
    T.BOOKING_EXPIRING: {
        "ru": ("Заявка скоро истечёт", "Осталось 5 мин, чтобы ответить: {service}, {when}."),
        "uz": ("Buyurtma muddati tugayapti", "Javob berish uchun 5 daqiqa qoldi: {service}, {when}."),
    },
    T.BOOKING_CONFIRMED: {
        "ru": ("Запись подтверждена", "{venue}: {service}, {when}."),
        "uz": ("Yozuv tasdiqlandi", "{venue}: {service}, {when}."),
    },
    T.BOOKING_REJECTED: {
        "ru": ("Запись отклонена", "{venue}: {service}, {when}. Выберите другое время."),
        "uz": ("Yozuv rad etildi", "{venue}: {service}, {when}. Boshqa vaqtni tanlang."),
    },
    T.BOOKING_EXPIRED: {
        "ru": ("Специалист не ответил", "{venue}: {service}, {when}. Выберите другое время."),
        "uz": ("Mutaxassis javob bermadi", "{venue}: {service}, {when}. Boshqa vaqtni tanlang."),
    },
    T.BOOKING_CANCELLED: {
        "ru": ("Запись отменена", "{service}, {when}."),
        "uz": ("Yozuv bekor qilindi", "{service}, {when}."),
    },
    T.BOOKING_REMINDER: {
        "ru": ("Напоминание о записи", "{venue}: {service}, {when}."),
        "uz": ("Yozuv haqida eslatma", "{venue}: {service}, {when}."),
    },
    T.JOIN_REQUEST: {
        "ru": ("Заявка на вступление", "{name} хочет работать в «{venue}»."),
        "uz": ("Qo'shilish so'rovi", "{name} «{venue}»da ishlamoqchi."),
    },
    T.JOIN_DECISION: {
        "ru": ("Решение по заявке", "«{venue}»: {decision}."),
        "uz": ("So'rov bo'yicha qaror", "«{venue}»: {decision}."),
    },
    T.VENUE_DECISION: {
        "ru": ("Решение модерации", "«{venue}»: {decision}. {reason}"),
        "uz": ("Moderatsiya qarori", "«{venue}»: {decision}. {reason}"),
    },
    T.ACCOUNT_BLOCKED: {
        "ru": ("Аккаунт заблокирован", "{reason}"),
        "uz": ("Akkaunt bloklandi", "{reason}"),
    },
}

WORDS = {
    "accepted": {"ru": "принята", "uz": "qabul qilindi"},
    "rejected": {"ru": "отклонена", "uz": "rad etildi"},
    "approved": {"ru": "одобрено", "uz": "tasdiqlandi"},
    "blocked": {"ru": "заблокировано", "uz": "bloklandi"},
}


def word(key, lang):
    return WORDS[key].get(lang, WORDS[key]["ru"])


def notify(user, type_, data=None, **params):
    """Создаёт уведомление и отправляет пуш после коммита транзакции."""
    if user is None:
        return None
    lang = user.language if user.language in ("ru", "uz") else "ru"
    title, body = TEMPLATES[type_][lang]
    params = {key: (value(lang) if callable(value) else value) for key, value in params.items()}
    notification = Notification.objects.create(
        user=user,
        type=type_,
        title=title.format(**params),
        body=body.format(**params).strip(),
        data=data or {},
    )
    transaction.on_commit(lambda: send_push(notification))
    return notification


def send_push(notification):
    tokens = list(notification.user.devices.values_list("token", flat=True))
    if not tokens:
        return
    payload = {"type": notification.type, "notification_id": str(notification.id)}
    payload.update({key: str(value) for key, value in notification.data.items()})
    if settings.PUSH_BACKEND == "expo":
        _send_expo(tokens, notification.title, notification.body, payload)
    elif settings.PUSH_BACKEND == "fcm":
        _send_fcm(tokens, notification.title, notification.body, payload)
    else:
        logger.info("PUSH to user %s: %s — %s %s", notification.user_id, notification.title, notification.body, payload)


def _send_expo(tokens, title, body, data):
    """Expo Push Service: сам доставляет через FCM (Android) и APNs (iOS)."""
    import requests

    from apps.accounts.models import Device

    messages = [{"to": token, "title": title, "body": body, "data": data, "sound": "default"} for token in tokens]
    try:
        response = requests.post("https://exp.host/--/api/v2/push/send", json=messages, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Ошибка отправки Expo push")
        return
    for token, ticket in zip(tokens, response.json().get("data", [])):
        if ticket.get("status") == "error" and (ticket.get("details") or {}).get("error") == "DeviceNotRegistered":
            Device.objects.filter(token=token).delete()


def _send_fcm(tokens, title, body, data):
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
    except ImportError:
        logger.error("PUSH_BACKEND=fcm, но пакет firebase-admin не установлен")
        return
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(settings.FCM_CREDENTIALS_FILE))
    message = messaging.MulticastMessage(
        tokens=tokens,
        notification=messaging.Notification(title=title, body=body),
        data=data,
    )
    try:
        response = messaging.send_each_for_multicast(message)
    except Exception:  # сеть или неверные ключи не должны ломать запрос пользователя
        logger.exception("Ошибка отправки FCM")
        return
    from apps.accounts.models import Device

    for token, result in zip(tokens, response.responses):
        if not result.success and isinstance(result.exception, messaging.UnregisteredError):
            Device.objects.filter(token=token).delete()
