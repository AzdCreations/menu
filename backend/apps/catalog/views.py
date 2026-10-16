from datetime import date

from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bookings.services import available_slots
from apps.core.exceptions import ApiError

from . import services
from .models import Category, Membership, ScheduleException, Service, Venue, VenuePhoto, WorkingHours
from .serializers import (
    CategorySerializer,
    MemberSerializer,
    MembershipSerializer,
    OwnVenueSerializer,
    PhotoSerializer,
    ScheduleExceptionSerializer,
    ServiceSerializer,
    VenueDetailSerializer,
    VenueHoursSerializer,
    VenueListSerializer,
    WorkingHoursSerializer,
    validate_week,
)

MAX_PHOTOS = 10
MAX_LIST = 200


# ------------------------------------------------------------------ публичный каталог


class CategoryListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = CategorySerializer
    pagination_class = None
    queryset = Category.objects.filter(is_active=True)


class VenueListView(APIView):
    """Список одобренных заведений: фильтр по направлению, поиск, сортировка по расстоянию."""

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter("category", int),
            OpenApiParameter("q", str),
            OpenApiParameter("lat", float),
            OpenApiParameter("lng", float),
            OpenApiParameter("radius_km", float),
        ],
        responses=VenueListSerializer(many=True),
    )
    def get(self, request):
        qs = Venue.objects.filter(status=Venue.Status.APPROVED, category__is_active=True).prefetch_related("photos")
        params = request.query_params
        if params.get("category"):
            qs = qs.filter(category_id=params["category"])
        if params.get("q"):
            qs = qs.filter(Q(name__icontains=params["q"]) | Q(address__icontains=params["q"]))
        try:
            lat, lng = float(params["lat"]), float(params["lng"])
        except (KeyError, ValueError):
            lat = lng = None
        if lat is not None:
            radius = min(float(params.get("radius_km") or 20), 100)
            venues = []
            for venue in qs.filter(**services.bbox(lat, lng, radius)):
                venue.distance_km = services.distance_km(lat, lng, venue.lat, venue.lng)
                if venue.distance_km <= radius:
                    venues.append(venue)
            venues.sort(key=lambda v: v.distance_km)
        else:
            venues = list(qs.order_by("name"))
        data = VenueListSerializer(venues[:MAX_LIST], many=True, context={"request": request}).data
        return Response(data)


class VenueDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(responses=VenueDetailSerializer)
    def get(self, request, pk):
        venue = get_object_or_404(
            Venue.objects.select_related("category").prefetch_related("photos", "hours"),
            pk=pk,
            status=Venue.Status.APPROVED,
        )
        context = {"request": request, "visible_memberships": list(services.visible_memberships([venue.id]))}
        return Response(VenueDetailSerializer(venue, context=context).data)


class SlotsView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(parameters=[OpenApiParameter("service", int, required=True), OpenApiParameter("date", str, required=True)])
    def get(self, request, membership_id):
        membership = get_object_or_404(
            services.visible_memberships().prefetch_related("working_hours", "exceptions", "venue__hours"), pk=membership_id
        )
        service = get_object_or_404(Service, pk=request.query_params.get("service"), membership=membership, is_active=True)
        try:
            day = date.fromisoformat(request.query_params.get("date", ""))
        except ValueError:
            raise ApiError("invalid_date", "Дата в формате ГГГГ-ММ-ДД.")
        slots = available_slots(membership, service, day)
        return Response({"date": day.isoformat(), "slots": [slot.isoformat() for slot in slots]})


# ------------------------------------------------------------------ заведение (специалист/владелец)


def _own_venue(request, pk, owner_only=True):
    venue = get_object_or_404(Venue.objects.prefetch_related("photos", "hours"), pk=pk)
    if venue.owner_id == request.user.id:
        return venue
    is_member = venue.memberships.filter(specialist=request.user, status__in=Membership.ACTIVE_STATUSES).exists()
    if owner_only or not is_member:
        raise ApiError("forbidden", "Действие доступно только владельцу заведения.", status.HTTP_403_FORBIDDEN)
    return venue


class ProVenueCreateView(APIView):
    @extend_schema(request=OwnVenueSerializer, responses=OwnVenueSerializer)
    def post(self, request):
        serializer = OwnVenueSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        venue, duplicates = services.create_venue(request.user, dict(serializer.validated_data))
        data = OwnVenueSerializer(venue, context={"request": request}).data
        data["duplicates"] = [{"id": d.id, "name": d.name, "address": d.address} for d in duplicates]
        return Response(data, status=status.HTTP_201_CREATED)


class ProVenueView(APIView):
    @extend_schema(responses=OwnVenueSerializer)
    def get(self, request, pk):
        venue = _own_venue(request, pk, owner_only=False)
        return Response(OwnVenueSerializer(venue, context={"request": request}).data)

    @extend_schema(request=OwnVenueSerializer, responses=OwnVenueSerializer)
    def patch(self, request, pk):
        venue = _own_venue(request, pk)
        serializer = OwnVenueSerializer(venue, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if venue.status == Venue.Status.REJECTED:
            # Исправленное заведение уходит на повторную модерацию без новой оплаты.
            serializer.save(status=Venue.Status.PENDING, decision_reason="")
        else:
            serializer.save()
        return Response(OwnVenueSerializer(venue, context={"request": request}).data)


class ProVenueHoursView(APIView):
    @extend_schema(request=VenueHoursSerializer(many=True))
    def put(self, request, pk):
        venue = _own_venue(request, pk)
        serializer = VenueHoursSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        validate_week(serializer.validated_data)
        with transaction.atomic():
            services.save_venue_hours(venue, serializer.validated_data)
        return Response(VenueHoursSerializer(venue.hours.all(), many=True).data)


class ProVenuePhotosView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request={"multipart/form-data": {"type": "object", "properties": {"image": {"type": "string", "format": "binary"}}}})
    def post(self, request, pk):
        venue = _own_venue(request, pk)
        if venue.photos.count() >= MAX_PHOTOS:
            raise ApiError("too_many_photos", f"Не больше {MAX_PHOTOS} фото.")
        serializer = PhotoSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(venue=venue, order=venue.photos.count())
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ProVenuePhotoDeleteView(APIView):
    def delete(self, request, pk, photo_id):
        venue = _own_venue(request, pk)
        photo = get_object_or_404(VenuePhoto, pk=photo_id, venue=venue)
        photo.image.delete(save=False)
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProVenueJoinView(APIView):
    @extend_schema(request=None, responses=MembershipSerializer)
    def post(self, request, pk):
        venue = get_object_or_404(Venue, pk=pk)
        membership = services.join_venue(request.user, venue)
        return Response(MembershipSerializer(membership, context={"request": request}).data, status=status.HTTP_201_CREATED)


class ProVenueMembersView(APIView):
    @extend_schema(responses=MemberSerializer(many=True))
    def get(self, request, pk):
        venue = _own_venue(request, pk)
        members = venue.memberships.exclude(status=Membership.Status.REJECTED).select_related("specialist", "venue")
        return Response(MemberSerializer(members, many=True).data)


class ProMemberActionView(APIView):
    """Владелец: approve / reject / remove специалиста."""

    @extend_schema(request=None, responses=MemberSerializer)
    def post(self, request, membership_id, action):
        membership = get_object_or_404(Membership.objects.select_related("venue", "specialist"), pk=membership_id)
        _own_venue(request, membership.venue_id)
        if action == "approve":
            services.decide_membership(membership, accept=True)
        elif action == "reject":
            services.decide_membership(membership, accept=False)
        elif action == "remove":
            services.end_membership(membership, Membership.Status.REMOVED, request.user)
        else:
            raise ApiError("unknown_action", "Неизвестное действие.", status.HTTP_404_NOT_FOUND)
        return Response(MemberSerializer(membership).data)


class ProTransferOwnerView(APIView):
    @extend_schema(request={"application/json": {"type": "object", "properties": {"membership_id": {"type": "integer"}}}})
    def post(self, request, pk):
        venue = _own_venue(request, pk)
        target = get_object_or_404(Membership, pk=request.data.get("membership_id"))
        services.transfer_owner(venue, target)
        return Response(OwnVenueSerializer(venue, context={"request": request}).data)


# ------------------------------------------------------------------ профиль специалиста


def _current_membership(request):
    membership = services.active_membership(request.user)
    if membership is None:
        raise ApiError("no_membership", "Вы ещё не состоите в заведении.", status.HTTP_404_NOT_FOUND)
    return membership


def _membership_qs():
    return Membership.objects.select_related("venue", "specialist").prefetch_related("services", "working_hours")


class ProMembershipView(APIView):
    @extend_schema(responses=MembershipSerializer)
    def get(self, request):
        membership = _membership_qs().get(pk=_current_membership(request).pk)
        return Response(MembershipSerializer(membership, context={"request": request}).data)

    @extend_schema(request=MembershipSerializer, responses=MembershipSerializer)
    def patch(self, request):
        membership = _current_membership(request)
        serializer = MembershipSerializer(membership, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        membership = _membership_qs().get(pk=membership.pk)
        return Response(MembershipSerializer(membership, context={"request": request}).data)


class ProMembershipPhotoView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request={"multipart/form-data": {"type": "object", "properties": {"photo": {"type": "string", "format": "binary"}}}})
    def post(self, request):
        membership = _current_membership(request)
        photo = request.FILES.get("photo")
        if not photo:
            raise ApiError("photo_required", "Прикрепите фото.")
        membership.photo = photo
        membership.full_clean(exclude=["venue", "specialist"])
        membership.save(update_fields=["photo", "updated_at"])
        return Response(MembershipSerializer(_membership_qs().get(pk=membership.pk), context={"request": request}).data)


class ProMembershipLeaveView(APIView):
    @extend_schema(request=None)
    def post(self, request):
        membership = _current_membership(request)
        services.end_membership(membership, Membership.Status.LEFT, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProServiceListView(generics.ListCreateAPIView):
    serializer_class = ServiceSerializer
    pagination_class = None

    def get_queryset(self):
        return Service.objects.filter(membership=_current_membership(self.request))

    def perform_create(self, serializer):
        serializer.save(membership=_current_membership(self.request))


class ProServiceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ServiceSerializer

    def get_queryset(self):
        return Service.objects.filter(membership=_current_membership(self.request))

    def perform_destroy(self, instance):
        # Услуга остаётся в истории записей, поэтому только скрываем её.
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class ProWorkingHoursView(APIView):
    @extend_schema(responses=WorkingHoursSerializer(many=True))
    def get(self, request):
        membership = _current_membership(request)
        return Response(WorkingHoursSerializer(membership.working_hours.all(), many=True).data)

    @extend_schema(request=WorkingHoursSerializer(many=True), responses=WorkingHoursSerializer(many=True))
    def put(self, request):
        """Полная замена недельного графика: передайте только рабочие дни."""
        membership = _current_membership(request)
        serializer = WorkingHoursSerializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)
        validate_week(serializer.validated_data)
        with transaction.atomic():
            membership.working_hours.all().delete()
            WorkingHours.objects.bulk_create(WorkingHours(membership=membership, **item) for item in serializer.validated_data)
        return Response(WorkingHoursSerializer(membership.working_hours.all(), many=True).data)


class ProExceptionListView(generics.ListCreateAPIView):
    serializer_class = ScheduleExceptionSerializer
    pagination_class = None

    def get_queryset(self):
        return ScheduleException.objects.filter(membership=_current_membership(self.request), date_to__gte=date.today())

    def perform_create(self, serializer):
        serializer.save(membership=_current_membership(self.request))


class ProExceptionDetailView(generics.DestroyAPIView):
    def get_queryset(self):
        return ScheduleException.objects.filter(membership=_current_membership(self.request))
