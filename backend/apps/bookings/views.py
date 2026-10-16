from datetime import datetime, timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Membership
from apps.catalog.services import active_membership
from apps.core.exceptions import ApiError

from . import services
from .models import Booking
from .serializers import (
    BlockSerializer,
    BookingCreateSerializer,
    BookingSerializer,
    ManualBookingSerializer,
    ReasonSerializer,
    SpecialistBookingSerializer,
)

BOOKING_RELATED = ("venue", "membership__specialist", "membership__venue", "client", "specialist")


class BookingCreateView(APIView):
    @extend_schema(request=BookingCreateSerializer, responses=BookingSerializer)
    def post(self, request):
        serializer = BookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        booking = services.create_client_booking(
            request.user, data["membership"], data["service"], data["start"], data.get("comment", ""), data.get("extra")
        )
        return Response(BookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class MyBookingsView(generics.ListAPIView):
    """«Мои записи» клиента: ?scope=upcoming|past."""

    serializer_class = BookingSerializer

    def get_queryset(self):
        services.expire_stale()  # дешёвая проверка: статусы актуальны на момент показа
        qs = Booking.objects.filter(client=self.request.user).select_related(*BOOKING_RELATED)
        now = timezone.now()
        if self.request.query_params.get("scope") == "past":
            return qs.filter(end__lt=now).order_by("-start")
        if self.request.query_params.get("scope") == "upcoming":
            return qs.filter(end__gte=now).order_by("start")
        return qs.order_by("-start")


def _get_booking(request, pk):
    booking = get_object_or_404(Booking.objects.select_related(*BOOKING_RELATED), pk=pk)
    if booking.client_id != request.user.id and not services.is_staff_of(request.user, booking):
        raise ApiError("forbidden", "Нет доступа к записи.", status.HTTP_403_FORBIDDEN)
    return booking


def _serialize(request, booking):
    booking.refresh_from_db()
    if services.is_staff_of(request.user, booking):
        return SpecialistBookingSerializer(booking).data
    return BookingSerializer(booking).data


class BookingDetailView(APIView):
    def get(self, request, pk):
        return Response(_serialize(request, _get_booking(request, pk)))


class BookingActionView(APIView):
    """confirm / reject / cancel / complete / no-show."""

    @extend_schema(request=ReasonSerializer)
    def post(self, request, pk, action):
        booking = _get_booking(request, pk)
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data.get("reason", "")
        if action == "confirm":
            services.confirm(booking, request.user)
        elif action == "reject":
            services.reject(booking, request.user, reason)
        elif action == "cancel":
            services.cancel(booking, request.user, reason)
        elif action == "complete":
            services.mark_visit(booking, request.user, Booking.Status.COMPLETED)
        elif action == "no-show":
            services.mark_visit(booking, request.user, Booking.Status.NO_SHOW)
        else:
            raise ApiError("unknown_action", "Неизвестное действие.", status.HTTP_404_NOT_FOUND)
        return Response(_serialize(request, booking))


def _target_membership(request, membership):
    """Своё членство или (для владельца) членство специалиста своего заведения."""
    if membership is None:
        membership = active_membership(request.user)
        if membership is None:
            raise ApiError("no_membership", "Вы ещё не состоите в заведении.", status.HTTP_404_NOT_FOUND)
        return membership
    if membership.specialist_id == request.user.id or membership.venue.owner_id == request.user.id:
        return membership
    raise ApiError("forbidden", "Нет доступа к этому специалисту.", status.HTTP_403_FORBIDDEN)


class ProBookingsView(APIView):
    """Календарь специалиста. Владелец может передать ?membership=<id> или ?venue=1 (все специалисты)."""

    @extend_schema(
        parameters=[
            OpenApiParameter("from", str, description="ГГГГ-ММ-ДД"),
            OpenApiParameter("to", str, description="ГГГГ-ММ-ДД, включительно"),
            OpenApiParameter("membership", int),
            OpenApiParameter("venue", bool),
            OpenApiParameter("status", str),
        ],
        responses=SpecialistBookingSerializer(many=True),
    )
    def get(self, request):
        params = request.query_params
        membership = None
        if params.get("membership"):
            membership = get_object_or_404(Membership.objects.select_related("venue"), pk=params["membership"])
        membership = _target_membership(request, membership)
        services.expire_stale(specialist_id=membership.specialist_id)

        qs = Booking.objects.select_related(*BOOKING_RELATED)
        if params.get("venue") in ("1", "true") and membership.venue.owner_id == request.user.id:
            qs = qs.filter(venue=membership.venue)
        else:
            qs = qs.filter(membership=membership)

        tz = services.venue_tz(membership.venue)
        try:
            day_from = datetime.fromisoformat(params["from"]).date() if params.get("from") else services.local_today(membership.venue)
            day_to = datetime.fromisoformat(params["to"]).date() if params.get("to") else day_from + timedelta(days=7)
        except ValueError:
            raise ApiError("invalid_date", "Дата в формате ГГГГ-ММ-ДД.")
        if (day_to - day_from).days > 62:
            raise ApiError("range_too_long", "Период не больше 2 месяцев.")
        start = datetime.combine(day_from, datetime.min.time(), tzinfo=tz)
        end = datetime.combine(day_to + timedelta(days=1), datetime.min.time(), tzinfo=tz)
        qs = qs.filter(start__lt=end, end__gt=start)
        if params.get("status"):
            qs = qs.filter(status__in=params["status"].split(","))
        return Response(SpecialistBookingSerializer(qs.order_by("start"), many=True).data)


class ProManualBookingView(APIView):
    @extend_schema(request=ManualBookingSerializer, responses=SpecialistBookingSerializer)
    def post(self, request):
        serializer = ManualBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not data.get("service") and not data.get("duration_minutes"):
            raise ApiError("duration_required", "Укажите услугу или длительность.")
        membership = _target_membership(request, data.get("membership"))
        booking = services.create_manual_booking(
            request.user,
            membership,
            data["start"],
            service=data.get("service"),
            duration_minutes=data.get("duration_minutes"),
            client_name=data.get("client_name", "") or "—",
            client_phone=data.get("client_phone", ""),
            comment=data.get("comment", ""),
        )
        return Response(SpecialistBookingSerializer(booking).data, status=status.HTTP_201_CREATED)


class ProBlockView(APIView):
    @extend_schema(request=BlockSerializer, responses=SpecialistBookingSerializer)
    def post(self, request):
        serializer = BlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        membership = _target_membership(request, data.get("membership"))
        minutes = int((data["end"] - data["start"]).total_seconds() // 60)
        booking = services.create_manual_booking(
            request.user, membership, data["start"], duration_minutes=minutes, comment=data.get("comment", "")
        )
        return Response(SpecialistBookingSerializer(booking).data, status=status.HTTP_201_CREATED)
