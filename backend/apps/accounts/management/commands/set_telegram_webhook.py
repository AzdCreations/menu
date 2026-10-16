import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Регистрирует вебхук бота: manage.py set_telegram_webhook https://api.example.uz"

    def add_arguments(self, parser):
        parser.add_argument("base_url", help="Публичный адрес бэкенда (https).")

    def handle(self, base_url, **options):
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_WEBHOOK_SECRET:
            raise CommandError("Задайте TELEGRAM_BOT_TOKEN и TELEGRAM_WEBHOOK_SECRET в .env")
        response = requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook",
            json={
                "url": base_url.rstrip("/") + "/api/v1/telegram/webhook",
                "secret_token": settings.TELEGRAM_WEBHOOK_SECRET,
                "allowed_updates": ["message"],
            },
            timeout=15,
        )
        self.stdout.write(response.text)
