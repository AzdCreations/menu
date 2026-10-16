from django.utils import timezone
from rest_framework import serializers

from .models import Device, User


class UserSerializer(serializers.ModelSerializer):
    pd_consent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "phone", "name", "language", "is_specialist", "is_staff", "status", "pd_consent", "created_at"]
        read_only_fields = fields

    def get_pd_consent(self, obj):
        return obj.pd_consent_at is not None


class MeUpdateSerializer(serializers.ModelSerializer):
    pd_consent = serializers.BooleanField(required=False, write_only=True)

    class Meta:
        model = User
        fields = ["name", "language", "pd_consent"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Укажите имя.")
        return value

    def update(self, instance, validated_data):
        consent = validated_data.pop("pd_consent", None)
        if consent and instance.pd_consent_at is None:
            instance.pd_consent_at = timezone.now()
        return super().update(instance, validated_data)


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ["token", "platform"]
        extra_kwargs = {"token": {"validators": []}}


class DevLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    name = serializers.CharField(required=False, allow_blank=True)


class AdminLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField()


def tokens_for(user):
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh), "user": UserSerializer(user).data}
