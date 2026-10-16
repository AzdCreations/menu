"""API веб-панели главного админа (/api/v1/admin/...). Все действия пишутся в журнал."""

from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, serializers, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import User
from apps.accounts.serializers import UserSerializer
from apps.bookings.models import Booking
from apps.bookings.serializers import SpecialistBookingSerializer
from apps.bookings.services import cancel, format_when
from apps.catalog.models import Category, Membership, Venue
from apps.catalog.serializers import CategorySerializer, MemberSerializer, PhotoSerializer, VenueHoursSerializer
from apps.notifications.models import Notification
from apps.notifications.services import notify, word

from .exceptions import ApiError, Conflict
from .models import SETTING_DEFAULTS, AuditLog, Setting, audit


class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class AdminMixin:
    permission_classes = [IsAdmin]


class AdminReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


def _reason(request, required=False):
    serializer = AdminReasonSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    reason = serializer.validated_data.get("reason", "").strip()
    if required and not reason:
        raise ApiError("reason_required", "Укажите причину.")
    return reason


# ------------------------------------------------------------------ направления


class AdminCategoryViewSet(AdminMixin, viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    pagination_class = None
    queryset = Category.objects.annotate(venues_count=Count("venues"))

    def perform_create(self, serializer):
        audit(self.request, "category.create", serializer.save(), data=serializer.data)

    def perform_update(self, serializer):
        audit(self.request, "category.update", serializer.save(), data=self.request.data)

    def perform_destroy(self, instance):
        if instance.venues.exists():
            raise Conflict("category_in_use", "В направлении есть заведения — скройте его вместо удаления.")
        audit(self.request, "category.delete", instance)
        instance.delete()


# ------------------------------------------------------------------ заведения


class AdminVenueSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name_ru", read_only=True)
    owner = UserSerializer(read_only=True)
    photos = PhotoSerializer(many=True, read_only=True)
    hours = VenueHoursSerializer(many=True, read_only=True)
    members = serializers.SerializerMethodField()
    possible_duplicate = serializers.SerializerMethodField()

    class Meta:
        model = Venue
        fields = [
            "id", "category", "category_name", "name", "address", "lat", "lng", "phone", "status", "decision_reason",
            "owner", "photos", "hours", "members", "possible_duplicate", "free_until", "created_at", "updated_at",
        ]

    def get_members(self, obj):
        return MemberSerializer(obj.memberships.exclude(status=Membership.Status.REJECTED), many=True).data

    def get_possible_duplicate(self, obj):
        dup = obj.possible_duplicate
        return {"id": dup.id, "name": dup.name, "address": dup.address, "status": dup.status} if dup else None


class AdminVenueListView(AdminMixin, generics.ListAPIView):
    serializer_class = AdminVenueSerializer

    @extend_schema(parameters=[OpenApiParameter("status", str), OpenApiParameter("q", str), OpenApiParameter("category", int)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = Venue.objects.select_related("category", "owner", "possible_duplicate").prefetch_related(
            "photos", "hours", "memberships__specialist", "memberships__venue"
        )
        params = self.request.query_params
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("category"):
            qs = qs.filter(category_id=params["category"])
        if params.get("q"):
            q = params["q"]
            qs = qs.filter(Q(name__icontains=q) | Q(address__icontains=q) | Q(owner__phone__icontains=q))
        # Очередь модерации — старые заявки первыми.
        return qs.order_by("created_at") if params.get("status") == Venue.Status.PENDING else qs.order_by("-created_at")


class AdminVenueDetailView(AdminMixin, generics.RetrieveAPIView):
    serializer_class = AdminVenueSerializer
    queryset = Venue.objects.select_related("category", "owner", "possible_duplicate")


def _cancel_future(bookings, actor, reason):
    for booking in bookings.filter(status__in=Booking.BUSY_STATUSES, start__gt=timezone.now()):
        if booking.status == Booking.Status.PENDING:
            booking.status = Booking.Status.REJECTED
            booking.status_reason = reason
            booking.save(update_fields=["status", "status_reason", "updated_at"])
            if booking.client:
                notify(booking.client, Notification.Type.BOOKING_REJECTED, data={"booking_id": booking.id},
                       venue=booking.venue.name, service=booking.service_name or "—",
                       when=format_when(booking))
        else:
            # Отмена от имени владельца заведения, чтобы клиент получил уведомление.
            cancel(booking, booking.venue.owner, reason)


class AdminVenueActionView(AdminMixin, APIView):
    """approve / reject / block / unblock."""

    @extend_schema(request=AdminReasonSerializer, responses=AdminVenueSerializer)
    def post(self, request, pk, action):
        with transaction.atomic():
            venue = get_object_or_404(Venue.objects.select_for_update(), pk=pk)
            if action == "approve":
                if venue.status != Venue.Status.PENDING:
                    raise Conflict("invalid_status", "Одобрить можно только заведение на модерации.")
                venue.status = Venue.Status.APPROVED
                venue.decision_reason = ""
                if venue.free_until is None:
                    venue.free_until = date.today() + timedelta(days=30 * Setting.get("free_period_months"))
                decision, reason = "approved", ""
            elif action == "reject":
                if venue.status != Venue.Status.PENDING:
                    raise Conflict("invalid_status", "Отклонить можно только заведение на модерации.")
                reason = _reason(request, required=True)
                venue.status, venue.decision_reason, decision = Venue.Status.REJECTED, reason, "rejected"
            elif action == "block":
                if venue.status == Venue.Status.BLOCKED:
                    raise Conflict("invalid_status", "Заведение уже заблокировано.")
                reason = _reason(request, required=True)
                venue.status, venue.decision_reason, decision = Venue.Status.BLOCKED, reason, "blocked"
            elif action == "unblock":
                if venue.status != Venue.Status.BLOCKED:
                    raise Conflict("invalid_status", "Заведение не заблокировано.")
                venue.status, venue.decision_reason, decision, reason = Venue.Status.APPROVED, "", "approved", ""
            else:
                raise ApiError("unknown_action", "Неизвестное действие.", status.HTTP_404_NOT_FOUND)
            venue.save()
            if action == "block":
                _cancel_future(Booking.objects.filter(venue=venue), request.user, "Заведение заблокировано")
            audit(request, f"venue.{action}", venue, reason=reason)
            notify(
                venue.owner,
                Notification.Type.VENUE_DECISION,
                data={"venue_id": venue.id},
                venue=venue.name,
                decision=lambda lang: word(decision, lang),
                reason=reason,
            )
        return Response(AdminVenueSerializer(venue, context={"request": request}).data)


# ------------------------------------------------------------------ пользователи


class AdminUserSerializer(UserSerializer):
    venues = serializers.SerializerMethodField()
    block_reason = serializers.CharField(read_only=True)
    bookings_count = serializers.IntegerField(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["block_reason", "venues", "bookings_count"]
        read_only_fields = fields

    def get_venues(self, obj):
        return [
            {"id": m.venue_id, "name": m.venue.name, "membership_status": m.status, "is_owner": m.venue.owner_id == obj.id}
            for m in obj.memberships.all()
            if m.status in Membership.ACTIVE_STATUSES
        ]


class AdminUserListView(AdminMixin, generics.ListAPIView):
    serializer_class = AdminUserSerializer

    @extend_schema(parameters=[OpenApiParameter("q", str), OpenApiParameter("role", str, enum=["client", "specialist", "staff"]), OpenApiParameter("status", str)])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        qs = User.objects.annotate(bookings_count=Count("bookings")).prefetch_related("memberships__venue")
        params = self.request.query_params
        if params.get("q"):
            qs = qs.filter(Q(phone__icontains=params["q"]) | Q(name__icontains=params["q"]))
        role = params.get("role")
        if role == "specialist":
            qs = qs.filter(is_specialist=True)
        elif role == "client":
            qs = qs.filter(is_specialist=False, is_staff=False)
        elif role == "staff":
            qs = qs.filter(is_staff=True)
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        return qs


class AdminUserDetailView(AdminMixin, generics.RetrieveAPIView):
    serializer_class = AdminUserSerializer
    queryset = User.objects.annotate(bookings_count=Count("bookings")).prefetch_related("memberships__venue")


class AdminUserActionView(AdminMixin, APIView):
    """block / unblock."""

    @extend_schema(request=AdminReasonSerializer, responses=AdminUserSerializer)
    def post(self, request, pk, action):
        user = get_object_or_404(User, pk=pk)
        if user.pk == request.user.pk or user.is_staff:
            raise ApiError("forbidden", "Нельзя блокировать админа.", status.HTTP_403_FORBIDDEN)
        if action == "block":
            if user.status != User.Status.ACTIVE:
                raise Conflict("invalid_status", "Пользователь уже заблокирован или удалён.")
            reason = _reason(request, required=True)
            with transaction.atomic():
                notify(user, Notification.Type.ACCOUNT_BLOCKED, reason=reason)
                user.status, user.block_reason = User.Status.BLOCKED, reason
                user.save(update_fields=["status", "block_reason", "updated_at"])
                for token in OutstandingToken.objects.filter(user=user):
                    BlacklistedToken.objects.get_or_create(token=token)
                _cancel_future(Booking.objects.filter(specialist=user), request.user, "Специалист недоступен")
                for booking in Booking.objects.filter(client=user, status__in=Booking.BUSY_STATUSES, start__gt=timezone.now()):
                    cancel(booking, user, "Аккаунт клиента заблокирован")
                audit(request, "user.block", user, reason=reason)
        elif action == "unblock":
            if user.status != User.Status.BLOCKED:
                raise Conflict("invalid_status", "Пользователь не заблокирован.")
            user.status, user.block_reason = User.Status.ACTIVE, ""
            user.save(update_fields=["status", "block_reason", "updated_at"])
            audit(request, "user.unblock", user)
        else:
            raise ApiError("unknown_action", "Неизвестное действие.", status.HTTP_404_NOT_FOUND)
        user = AdminUserDetailView.queryset.get(pk=user.pk)
        return Response(AdminUserSerializer(user).data)


# ------------------------------------------------------------------ записи, статистика, настройки, журнал


class AdminBookingListView(AdminMixin, generics.ListAPIView):
    serializer_class = SpecialistBookingSerializer

    def get_queryset(self):
        qs = Booking.objects.select_related("venue", "membership__specialist", "client").order_by("-start")
        params = self.request.query_params
        if params.get("venue"):
            qs = qs.filter(venue_id=params["venue"])
        if params.get("status"):
            qs = qs.filter(status=params["status"])
        if params.get("user"):
            qs = qs.filter(Q(client_id=params["user"]) | Q(specialist_id=params["user"]))
        return qs


class AdminStatsView(AdminMixin, APIView):
    @extend_schema(parameters=[OpenApiParameter("days", int, description="Период в днях, по умолчанию 30")])
    def get(self, request):
        days = min(int(request.query_params.get("days") or 30), 365)
        since = timezone.now() - timedelta(days=days)
        bookings = Booking.objects.filter(kind=Booking.Kind.BOOKING, created_at__gte=since)
        by_category = (
            Venue.objects.filter(status=Venue.Status.APPROVED)
            .values("category__name_ru")
            .annotate(venues=Count("id"))
            .order_by("category__name_ru")
        )
        return Response({
            "period_days": days,
            "venues": {row["status"]: row["n"] for row in Venue.objects.values("status").annotate(n=Count("id"))},
            "venues_by_category": list(by_category),
            "specialists": Membership.objects.filter(status=Membership.Status.ACCEPTED).values("specialist").distinct().count(),
            "clients": User.objects.filter(status=User.Status.ACTIVE, is_staff=False).count(),
            "new_users": User.objects.filter(created_at__gte=since).count(),
            "bookings": {row["status"]: row["n"] for row in bookings.values("status").annotate(n=Count("id"))},
            "bookings_total": bookings.count(),
        })


class AdminSettingsView(AdminMixin, APIView):
    def get(self, request):
        return Response(Setting.all_values())

    @extend_schema(request={"application/json": {"type": "object"}})
    def patch(self, request):
        if not isinstance(request.data, dict):
            raise ApiError("validation_error", "Ожидается объект.")
        for key, value in request.data.items():
            if key not in SETTING_DEFAULTS:
                raise ApiError("unknown_setting", f"Неизвестная настройка: {key}.")
            expected = type(SETTING_DEFAULTS[key])
            if expected is int and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                raise ApiError("validation_error", f"{key}: ожидается неотрицательное целое число.")
            if expected is bool and not isinstance(value, bool):
                raise ApiError("validation_error", f"{key}: ожидается true/false.")
        for key, value in request.data.items():
            row, _ = Setting.objects.update_or_create(key=key, defaults={"value": value})
            audit(request, "setting.update", row, value=value)
        return Response(Setting.all_values())


class AuditLogSerializer(serializers.ModelSerializer):
    actor_phone = serializers.CharField(source="actor.phone", default="", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "actor_phone", "action", "object_type", "object_id", "data", "ip", "created_at"]


class AdminAuditLogView(AdminMixin, generics.ListAPIView):
    serializer_class = AuditLogSerializer
    queryset = AuditLog.objects.select_related("actor")
