import hmac

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from apps.core.exceptions import ApiError, error_response

from . import telegram
from .models import Device, TelegramLogin, User, normalize_phone
from .serializers import (
    AdminLoginSerializer,
    DeviceSerializer,
    DevLoginSerializer,
    MeUpdateSerializer,
    UserSerializer,
    tokens_for,
)


class TelegramStartThrottle(AnonRateThrottle):
    scope = "telegram_start"


class TelegramStartView(APIView):
    """Шаг 1 входа: одноразовый токен и ссылка на бота."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [TelegramStartThrottle]

    def post(self, request):
        login = TelegramLogin.objects.create()
        return Response(
            {"token": login.token, "bot_url": telegram.bot_url(login.token), "expires_at": login.expires_at},
            status=status.HTTP_201_CREATED,
        )


class TelegramStatusView(APIView):
    """Шаг 2: приложение опрашивает статус; после подтверждения получает JWT (один раз)."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, token):
        with transaction.atomic():
            login = TelegramLogin.objects.select_for_update().filter(token=token).first()
            if login is None:
                raise Http404
            if login.status == TelegramLogin.Status.PENDING and login.is_expired:
                login.status = TelegramLogin.Status.EXPIRED
                login.save(update_fields=["status"])
            if login.status != TelegramLogin.Status.CONFIRMED:
                return Response({"status": login.status})
            login.status = TelegramLogin.Status.USED
            login.save(update_fields=["status"])
            return Response({"status": "confirmed", **tokens_for(login.user)})


class TelegramWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(exclude=True)
    def post(self, request):
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not settings.TELEGRAM_WEBHOOK_SECRET or not hmac.compare_digest(secret, settings.TELEGRAM_WEBHOOK_SECRET):
            return Response(status=status.HTTP_403_FORBIDDEN)
        telegram.handle_update(request.data)
        return Response({"ok": True})


class DevLoginView(APIView):
    """Вход по номеру без проверки — только при DEV_LOGIN_ENABLED (разработка)."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    @extend_schema(request=DevLoginSerializer)
    def post(self, request):
        if not settings.DEV_LOGIN_ENABLED:
            raise Http404
        serializer = DevLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = normalize_phone(serializer.validated_data["phone"])
        if not phone:
            raise ApiError("invalid_phone", "Номер должен быть в формате +998XXXXXXXXX.")
        user, _ = User.objects.get_or_create(phone=phone, defaults={"name": serializer.validated_data.get("name", "")})
        if not user.is_active:
            raise ApiError("user_blocked", "Аккаунт заблокирован.", 403)
        return Response(tokens_for(user))


class AdminLoginView(APIView):
    """Вход в веб-панель главного админа: телефон и пароль."""

    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [TelegramStartThrottle]

    @extend_schema(request=AdminLoginSerializer)
    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = normalize_phone(serializer.validated_data["phone"]) or ""
        user = authenticate(request, phone=phone, password=serializer.validated_data["password"])
        if user is None or not user.is_staff:
            raise ApiError("invalid_credentials", "Неверный телефон или пароль.", 401)
        return Response(tokens_for(user))


class LogoutView(APIView):
    def post(self, request):
        try:
            RefreshToken(request.data.get("refresh", "")).blacklist()
        except TokenError:
            pass
        Device.objects.filter(user=request.user, token=request.data.get("device_token", "")).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    @extend_schema(responses=UserSerializer)
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    @extend_schema(request=MeUpdateSerializer, responses=UserSerializer)
    def patch(self, request):
        serializer = MeUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)

    def delete(self, request):
        """Удаление аккаунта (требование App Store и Google Play): данные обезличиваются."""
        from apps.bookings.models import Booking
        from apps.bookings.services import cancel
        from apps.catalog.models import Membership, Venue

        user = request.user
        if Venue.objects.filter(owner=user).exclude(status=Venue.Status.CLOSED).exists():
            return error_response(
                "owner_must_transfer", "Сначала передайте права владельца или закройте заведение.", status.HTTP_409_CONFLICT
            )
        now = timezone.now()
        for booking in Booking.objects.filter(client=user, status__in=Booking.BUSY_STATUSES, start__gt=now):
            cancel(booking, user, "Аккаунт удалён")
        with transaction.atomic():
            for membership in Membership.objects.filter(specialist=user, status__in=Membership.ACTIVE_STATUSES):
                for booking in Booking.objects.filter(membership=membership, status__in=Booking.BUSY_STATUSES, start__gt=now):
                    booking.status = Booking.Status.CANCELLED_SPECIALIST
                    booking.status_reason = "Аккаунт специалиста удалён"
                    booking.save(update_fields=["status", "status_reason", "updated_at"])
                membership.status = Membership.Status.LEFT
                membership.save(update_fields=["status", "updated_at"])
            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)
            user.devices.all().delete()
            user.phone = f"del{user.id}"[:13]
            user.name = ""
            user.telegram_id = None
            user.status = User.Status.DELETED
            user.set_unusable_password()
            user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BecomeSpecialistView(APIView):
    @extend_schema(request=None, responses=UserSerializer)
    def post(self, request):
        request.user.is_specialist = True
        request.user.save(update_fields=["is_specialist", "updated_at"])
        return Response(UserSerializer(request.user).data)


class DeviceView(APIView):
    @extend_schema(request=DeviceSerializer)
    def post(self, request):
        serializer = DeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        Device.objects.update_or_create(
            token=serializer.validated_data["token"],
            defaults={"user": request.user, "platform": serializer.validated_data["platform"]},
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
