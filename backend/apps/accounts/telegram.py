"""Вход через Telegram-бота: бот получает от пользователя его собственный контакт.

Поток (раздел 3.1 ТЗ):
1. Приложение создаёт TelegramLogin и открывает t.me/<бот>?start=<token>.
2. /start <token> — бот запоминает Telegram user id и просит «Поделиться номером».
3. Контакт принимается, только если contact.user_id совпадает с отправителем.
4. Аккаунт находится или создаётся по номеру, вход помечается подтверждённым.
"""

import logging

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import TelegramLogin, User, normalize_phone

logger = logging.getLogger(__name__)

TEXT = {
    "ask_contact": "Нажмите кнопку ниже, чтобы подтвердить номер.\nTelefon raqamingizni tasdiqlash uchun quyidagi tugmani bosing.",
    "share_button": "📱 Поделиться номером / Raqamni yuborish",
    "open_from_app": "Откройте бота из приложения, чтобы войти.\nKirish uchun botni ilovadan oching.",
    "link_expired": "Ссылка для входа устарела. Начните вход в приложении заново.\nKirish havolasi eskirgan. Ilovada qaytadan boshlang.",
    "own_contact_only": "Отправьте свой номер кнопкой «Поделиться номером».\nO'z raqamingizni tugma orqali yuboring.",
    "uz_only": "Сейчас поддерживаются только номера Узбекистана (+998).\nHozircha faqat O'zbekiston raqamlari (+998).",
    "blocked": "Аккаунт заблокирован. Напишите в поддержку.\nAkkaunt bloklangan.",
    "done": "Готово! Вернитесь в приложение.\nTayyor! Ilovaga qayting.",
    "back_button": "Вернуться в приложение / Ilovaga qaytish",
}


def bot_url(token):
    return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start={token}"


def send_message(chat_id, text, reply_markup=None):
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.info("TELEGRAM to %s: %s", chat_id, text)
        return
    payload = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage", json=payload, timeout=10
        ).raise_for_status()
    except requests.RequestException:
        logger.exception("Не удалось отправить сообщение в Telegram")


def handle_update(update):
    message = update.get("message") or {}
    sender = message.get("from") or {}
    chat_id = (message.get("chat") or {}).get("id")
    if not sender.get("id") or not chat_id:
        return
    if "contact" in message:
        _handle_contact(sender, chat_id, message["contact"])
    elif (message.get("text") or "").startswith("/start"):
        _handle_start(sender, chat_id, message["text"])


def _handle_start(sender, chat_id, text):
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send_message(chat_id, TEXT["open_from_app"])
        return
    login = TelegramLogin.objects.filter(token=parts[1].strip(), status=TelegramLogin.Status.PENDING).first()
    if login is None or login.is_expired:
        send_message(chat_id, TEXT["link_expired"])
        return
    login.telegram_user_id = sender["id"]
    login.save(update_fields=["telegram_user_id"])
    send_message(
        chat_id,
        TEXT["ask_contact"],
        {
            "keyboard": [[{"text": TEXT["share_button"], "request_contact": True}]],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        },
    )


def _handle_contact(sender, chat_id, contact):
    if contact.get("user_id") != sender["id"]:
        send_message(chat_id, TEXT["own_contact_only"])
        return
    phone = normalize_phone(contact.get("phone_number"))
    if not phone:
        send_message(chat_id, TEXT["uz_only"], {"remove_keyboard": True})
        return

    with transaction.atomic():
        login = (
            TelegramLogin.objects.select_for_update()
            .filter(telegram_user_id=sender["id"], status=TelegramLogin.Status.PENDING, expires_at__gt=timezone.now())
            .order_by("-created_at")
            .first()
        )
        if login is None:
            send_message(chat_id, TEXT["link_expired"], {"remove_keyboard": True})
            return

        user, created = User.objects.get_or_create(phone=phone, defaults={"name": _full_name(sender)})
        if created:
            user.set_unusable_password()
        if user.status != User.Status.ACTIVE:
            login.status = TelegramLogin.Status.EXPIRED
            login.save(update_fields=["status"])
            send_message(chat_id, TEXT["blocked"], {"remove_keyboard": True})
            return
        if user.telegram_id != sender["id"]:
            # Этот Telegram мог быть привязан к старому номеру — переносим привязку.
            User.objects.filter(telegram_id=sender["id"]).exclude(pk=user.pk).update(telegram_id=None)
            user.telegram_id = sender["id"]
        user.save()

        login.status = TelegramLogin.Status.CONFIRMED
        login.phone = phone
        login.user = user
        login.save(update_fields=["status", "phone", "user"])

    send_message(chat_id, TEXT["done"], {"remove_keyboard": True})
    if settings.APP_RETURN_URL:
        send_message(
            chat_id,
            "👇",
            {"inline_keyboard": [[{"text": TEXT["back_button"], "url": settings.APP_RETURN_URL}]]},
        )


def _full_name(sender):
    return " ".join(filter(None, [sender.get("first_name"), sender.get("last_name")]))[:100]
