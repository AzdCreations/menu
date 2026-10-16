"""Демо-данные для разработки: направления, админ, заведение с мастером и услугами."""

from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.catalog.models import Category, Membership, Service, Venue, VenueHours, WorkingHours


class Command(BaseCommand):
    help = "Создаёт демо-данные (идемпотентно)."

    def add_arguments(self, parser):
        parser.add_argument("--admin-password", default="admin12345")

    @transaction.atomic
    def handle(self, *args, admin_password, **options):
        salon, _ = Category.objects.get_or_create(
            name_ru="Салоны и парикмахерские",
            defaults={"name_uz": "Salonlar va sartaroshxonalar", "specialist_name_ru": "мастер",
                      "specialist_name_uz": "usta", "icon": "scissors", "order": 1},
        )
        Category.objects.get_or_create(
            name_ru="Стоматологии",
            defaults={
                "name_uz": "Stomatologiyalar", "specialist_name_ru": "врач", "specialist_name_uz": "shifokor",
                "icon": "tooth", "order": 2,
                "booking_fields": [{"key": "reason", "label_ru": "Причина визита", "label_uz": "Tashrif sababi",
                                    "type": "select", "options": ["Осмотр", "Боль", "Чистка", "Другое"], "required": True}],
            },
        )

        admin = User.objects.filter(phone="+998900000000").first()
        if admin is None:
            User.objects.create_superuser("+998900000000", admin_password, name="Админ")

        owner, _ = User.objects.get_or_create(phone="+998901111111", defaults={"name": "Дилноза", "is_specialist": True})
        venue = Venue.objects.filter(owner=owner).first()
        if venue is None:
            venue = Venue.objects.create(
                category=salon, owner=owner, name="Salon Dilnoza", address="Ташкент, ул. Амира Темура, 15",
                lat="41.311081", lng="69.279737", phone="+998901111111", status=Venue.Status.APPROVED,
                free_until=date.today() + timedelta(days=180),
            )
            for day in range(7):
                VenueHours.objects.create(venue=venue, weekday=day, start=time(9), end=time(21), is_day_off=day == 6)
            membership = Membership.objects.create(
                venue=venue, specialist=owner, status=Membership.Status.ACCEPTED, display_name="Дилноза"
            )
            Service.objects.create(membership=membership, name="Женская стрижка", duration_minutes=60, price=120000)
            Service.objects.create(membership=membership, name="Укладка", duration_minutes=30, price=60000, price_from=True)
            Service.objects.create(membership=membership, name="Консультация", duration_minutes=15)
            for day in range(6):
                WorkingHours.objects.create(
                    membership=membership, weekday=day, start=time(10), end=time(19),
                    breaks=[{"start": "13:00", "end": "14:00"}],
                )
        User.objects.get_or_create(phone="+998902222222", defaults={"name": "Клиент Демо"})
        self.stdout.write(self.style.SUCCESS(
            "Готово. Админ: +998900000000 / пароль из --admin-password. "
            "Мастер (владелец): +998901111111. Клиент: +998902222222 (вход через dev-login)."
        ))
