from datetime import time

from rest_framework import serializers

from .models import Category, Membership, ScheduleException, Service, Venue, VenueHours, VenuePhoto, WorkingHours

BOOKING_FIELD_TYPES = {"text", "select", "bool"}


class CategorySerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True)
    specialist_name = serializers.CharField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id", "name", "specialist_name", "name_uz", "name_ru", "specialist_name_uz", "specialist_name_ru",
            "icon", "order", "is_active", "booking_fields",
        ]

    def validate_booking_fields(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Ожидается список полей.")
        keys = set()
        for field in value:
            if not isinstance(field, dict) or not field.get("key") or field.get("type", "text") not in BOOKING_FIELD_TYPES:
                raise serializers.ValidationError("Каждое поле: key, label_uz, label_ru, type (text|select|bool).")
            if field["key"] in keys:
                raise serializers.ValidationError(f"Повтор ключа {field['key']}.")
            if field.get("type") == "select" and not field.get("options"):
                raise serializers.ValidationError(f"У поля {field['key']} нет вариантов выбора.")
            keys.add(field["key"])
        return value


class PhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VenuePhoto
        fields = ["id", "image", "order"]


class VenueHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = VenueHours
        fields = ["weekday", "start", "end", "is_day_off"]

    def validate(self, attrs):
        if not attrs.get("is_day_off"):
            if not attrs.get("start") or not attrs.get("end") or attrs["start"] >= attrs["end"]:
                raise serializers.ValidationError("Укажите начало и конец рабочего дня (начало раньше конца).")
        return attrs


def validate_week(items):
    weekdays = [item["weekday"] for item in items]
    if len(weekdays) != len(set(weekdays)):
        raise serializers.ValidationError("День недели указан дважды.")
    return items


class PublicServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "duration_minutes", "price", "price_from"]


class PublicSpecialistSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="public_name")
    services = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ["id", "name", "photo", "bio", "services"]

    def get_services(self, obj):
        return PublicServiceSerializer([s for s in obj.services.all() if s.is_active], many=True).data


class VenueListSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(read_only=True)
    cover = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()

    class Meta:
        model = Venue
        fields = ["id", "category", "name", "address", "lat", "lng", "phone", "cover", "distance_km"]

    def get_cover(self, obj):
        photos = list(obj.photos.all())
        if not photos:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(photos[0].image.url) if request else photos[0].image.url

    def get_distance_km(self, obj):
        distance = getattr(obj, "distance_km", None)
        return round(distance, 2) if distance is not None else None


class VenueDetailSerializer(VenueListSerializer):
    photos = PhotoSerializer(many=True, read_only=True)
    hours = VenueHoursSerializer(many=True, read_only=True)
    specialists = serializers.SerializerMethodField()
    specialist_name = serializers.CharField(source="category.specialist_name", read_only=True)
    booking_fields = serializers.JSONField(source="category.booking_fields", read_only=True)

    class Meta(VenueListSerializer.Meta):
        fields = VenueListSerializer.Meta.fields + ["photos", "hours", "specialists", "specialist_name", "booking_fields"]

    def get_specialists(self, obj):
        visible = self.context.get("visible_memberships", [])
        return PublicSpecialistSerializer(visible, many=True, context=self.context).data


class OwnVenueSerializer(serializers.ModelSerializer):
    """Заведение для владельца и сотрудников: со статусом модерации."""

    photos = PhotoSerializer(many=True, read_only=True)
    hours = VenueHoursSerializer(many=True, required=False)
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Venue
        fields = [
            "id", "category", "name", "address", "lat", "lng", "phone", "status", "decision_reason",
            "photos", "hours", "is_owner", "created_at",
        ]
        read_only_fields = ["status", "decision_reason", "created_at"]

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return bool(request and obj.owner_id == request.user.id)

    def validate_category(self, value):
        if not value.is_active:
            raise serializers.ValidationError("Направление недоступно.")
        return value

    def validate_hours(self, value):
        return validate_week(value)

    def update(self, instance, validated_data):
        validated_data.pop("hours", None)
        validated_data.pop("category", None)  # направление после создания не меняется
        return super().update(instance, validated_data)


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["id", "name", "duration_minutes", "price", "price_from", "is_active"]


def _parse_hhmm(value):
    try:
        hours, minutes = value.split(":")
        return time(int(hours), int(minutes))
    except (AttributeError, ValueError):
        raise serializers.ValidationError("Время в формате ЧЧ:ММ.")


class WorkingHoursSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkingHours
        fields = ["weekday", "start", "end", "breaks"]

    def validate(self, attrs):
        if attrs["start"] >= attrs["end"]:
            raise serializers.ValidationError("Начало должно быть раньше конца.")
        breaks = attrs.get("breaks") or []
        if not isinstance(breaks, list):
            raise serializers.ValidationError("Перерывы — список.")
        clean = []
        for item in breaks:
            if not isinstance(item, dict):
                raise serializers.ValidationError("Перерыв: {start, end}.")
            start, end = _parse_hhmm(item.get("start")), _parse_hhmm(item.get("end"))
            if not (attrs["start"] <= start < end <= attrs["end"]):
                raise serializers.ValidationError("Перерыв должен быть внутри рабочего времени.")
            clean.append({"start": start.strftime("%H:%M"), "end": end.strftime("%H:%M")})
        attrs["breaks"] = clean
        return attrs


class ScheduleExceptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduleException
        fields = ["id", "date_from", "date_to", "kind", "start", "end"]

    def validate(self, attrs):
        if attrs["date_from"] > attrs["date_to"]:
            raise serializers.ValidationError("Дата начала позже даты конца.")
        if attrs["kind"] == ScheduleException.Kind.CUSTOM:
            if not attrs.get("start") or not attrs.get("end") or attrs["start"] >= attrs["end"]:
                raise serializers.ValidationError("Для «другого времени» укажите начало и конец.")
        else:
            attrs["start"] = attrs["end"] = None
        return attrs


class VenueShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = ["id", "name", "address", "status", "category", "owner"]


class MembershipSerializer(serializers.ModelSerializer):
    """Профиль специалиста в заведении (для самого специалиста)."""

    venue = VenueShortSerializer(read_only=True)
    is_owner = serializers.BooleanField(read_only=True)
    public_name = serializers.CharField(read_only=True)
    services = ServiceSerializer(many=True, read_only=True)
    working_hours = WorkingHoursSerializer(many=True, read_only=True)

    class Meta:
        model = Membership
        fields = [
            "id", "venue", "status", "is_owner", "public_name", "display_name", "photo", "bio", "auto_confirm",
            "slot_step_minutes", "min_lead_minutes", "horizon_days", "buffer_minutes", "services", "working_hours",
        ]
        read_only_fields = ["status", "photo"]


class MemberSerializer(serializers.ModelSerializer):
    """Состав заведения для владельца."""

    name = serializers.CharField(source="public_name", read_only=True)
    phone = serializers.CharField(source="specialist.phone", read_only=True)
    is_owner = serializers.BooleanField(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "name", "phone", "status", "is_owner", "created_at"]
