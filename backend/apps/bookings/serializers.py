from rest_framework import serializers

from apps.catalog.models import Membership, Service

from .models import Booking


class BookingSerializer(serializers.ModelSerializer):
    venue_name = serializers.CharField(source="venue.name", read_only=True)
    venue_address = serializers.CharField(source="venue.address", read_only=True)
    venue_phone = serializers.CharField(source="venue.phone", read_only=True)
    specialist_name = serializers.CharField(source="membership.public_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id", "kind", "source", "status", "status_label", "status_reason",
            "venue", "venue_name", "venue_address", "venue_phone",
            "membership", "specialist_name", "service", "service_name", "price", "duration_minutes",
            "start", "end", "comment", "extra", "respond_by", "created_at",
        ]
        read_only_fields = fields


class SpecialistBookingSerializer(BookingSerializer):
    """Для специалиста: данные клиента. Телефон — только у активной записи (раздел 12 ТЗ)."""

    client_name = serializers.SerializerMethodField()
    client_phone = serializers.SerializerMethodField()

    class Meta(BookingSerializer.Meta):
        fields = BookingSerializer.Meta.fields + ["client_name", "client_phone"]
        read_only_fields = fields

    def get_client_name(self, obj):
        return obj.client_name or (obj.client.name if obj.client else "")

    def get_client_phone(self, obj):
        if obj.status not in Booking.BUSY_STATUSES:
            return ""
        return obj.client_phone or (obj.client.phone if obj.client else "")


class BookingCreateSerializer(serializers.Serializer):
    membership = serializers.PrimaryKeyRelatedField(queryset=Membership.objects.select_related("venue__category", "specialist"))
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all())
    start = serializers.DateTimeField()
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)
    extra = serializers.JSONField(required=False)

    def validate_extra(self, value):
        if value is not None and not isinstance(value, dict):
            raise serializers.ValidationError("Ожидается объект.")
        return value


class ManualBookingSerializer(serializers.Serializer):
    membership = serializers.PrimaryKeyRelatedField(
        queryset=Membership.objects.select_related("venue", "specialist"), required=False
    )
    start = serializers.DateTimeField()
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.all(), required=False, allow_null=True)
    duration_minutes = serializers.IntegerField(required=False, min_value=5, max_value=12 * 60)
    client_name = serializers.CharField(required=False, allow_blank=True, max_length=100)
    client_phone = serializers.CharField(required=False, allow_blank=True, max_length=20)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)


class BlockSerializer(serializers.Serializer):
    membership = serializers.PrimaryKeyRelatedField(
        queryset=Membership.objects.select_related("venue", "specialist"), required=False
    )
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs):
        if attrs["end"] <= attrs["start"]:
            raise serializers.ValidationError("Конец должен быть позже начала.")
        if (attrs["end"] - attrs["start"]).total_seconds() > 24 * 3600:
            raise serializers.ValidationError("Блокировка не длиннее суток; для отпуска используйте исключения графика.")
        return attrs


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
