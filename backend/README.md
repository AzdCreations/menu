# Бэкенд платформы бронирования

Django + Django REST Framework + PostgreSQL. Реализует MVP по ТЗ (этапы 1–4): вход через Telegram-бота, каталог
направлений и заведений, модерацию, специалистов и их график, расчёт свободных окон, запись со статусами,
уведомления и API веб-панели админа.

## Быстрый старт (локально)

Нужны Python 3.12+ и PostgreSQL 14+ (с расширением `btree_gist`, оно входит в стандартный PostgreSQL).

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cp .env.example .env            # для разработки поставьте DJANGO_DEBUG=1 и DEV_LOGIN_ENABLED=1
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo          # демо-направления, админ, салон с мастером
.venv/bin/python manage.py runserver 0.0.0.0:8000
```

В отдельном терминале — фоновые задачи (истечение заявок через 10 минут, напоминания, автозавершение):

```bash
.venv/bin/python manage.py run_periodic --loop
```

- Документация API (Swagger): http://localhost:8000/api/v1/docs
- Django-админка (запасной вариант): http://localhost:8000/django-admin/
- Демо-доступы после `seed_demo`: админ `+998900000000` / `admin12345`, мастер `+998901111111`, клиент `+998902222222`
  (мастер и клиент входят через dev-login, пока не настроен бот).

## Docker

```bash
cd backend
cp .env.example .env   # заполните
docker compose up --build
docker compose exec web python manage.py seed_demo
```

Поднимаются три контейнера: `db` (PostgreSQL 16), `web` (gunicorn на порту 8000), `scheduler` (фоновые задачи).

## Вход через Telegram

1. Создайте бота у [@BotFather](https://t.me/BotFather), впишите `TELEGRAM_BOT_TOKEN` и `TELEGRAM_BOT_USERNAME` в `.env`.
2. Придумайте случайную строку для `TELEGRAM_WEBHOOK_SECRET`.
3. Бэкенд должен быть доступен по HTTPS. Зарегистрируйте вебхук:
   `python manage.py set_telegram_webhook https://api.ваш-домен.uz`
4. В `APP_RETURN_URL` можно указать deep link приложения (`bron://`) — бот покажет кнопку «Вернуться в приложение».

Порядок входа: приложение вызывает `POST /auth/telegram/start`, открывает `t.me/<бот>?start=<token>`, пользователь
нажимает «Поделиться номером», приложение опрашивает `GET /auth/telegram/status/<token>` и получает JWT.
Бот принимает только собственный контакт пользователя и только номера +998.

## Пуш-уведомления

`PUSH_BACKEND`:
- `log` — уведомления пишутся в базу и в лог (разработка);
- `expo` — через Expo Push Service (приложение в `mobile/` регистрирует Expo push-токены);
- `fcm` — напрямую через Firebase (нужен `pip install firebase-admin` и `FCM_CREDENTIALS_FILE`).

## Тесты

```bash
.venv/bin/pytest
```

Тестам нужен доступ к PostgreSQL (создаётся тестовая база). Покрыты вход через Telegram, расчёт окон, статусы записи,
истечение заявок, защита от двойной записи (в том числе два одновременных запроса), модерация, вступление в заведение,
блокировки и настройки админа.

## Структура

| Приложение | Что внутри |
| --- | --- |
| `apps/accounts` | Пользователь (один аккаунт — клиент и специалист), вход через Telegram, устройства для пушей |
| `apps/catalog` | Направления, заведения, фото, график заведения, членство, услуги, график специалиста, исключения |
| `apps/bookings` | Запись, история статусов, расчёт окон (`services.py`), фоновые задачи |
| `apps/notifications` | Уведомления на языке пользователя и отправка пушей |
| `apps/core` | Настройки платформы, журнал действий админа, API веб-панели (`admin_api.py`), единый формат ошибок |

Ключевые правила:
- Пересечение записей у специалиста запрещено ограничением PostgreSQL (`booking_no_overlap_per_specialist`),
  время занимают статусы «Ожидает подтверждения» и «Подтверждена». При конфликте API отвечает `409 slot_taken`.
- Заявка ждёт ответа `booking_response_minutes` (по умолчанию 10 минут), затем переходит в «Истекла».
- Все сроки и лимиты меняются в настройках веб-панели (`/api/v1/admin/settings`).
- Ошибки API: `{"code": "...", "message": "...", "fields": {...}}`.

## Не вошло в MVP

Оплата взноса (флаг `payment_enabled` уже есть), чаты с поддержкой, жалобы, кнопка «Это моё заведение», подписка.
