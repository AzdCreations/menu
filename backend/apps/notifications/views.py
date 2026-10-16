from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "type", "title", "body", "data", "is_read", "created_at"]


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data["unread"] = Notification.objects.filter(user=request.user, is_read=False).count()
        return response


class NotificationReadView(APIView):
    """Отметить прочитанными: {"ids": [...]} или пустое тело — все."""

    @extend_schema(request={"application/json": {"type": "object", "properties": {"ids": {"type": "array", "items": {"type": "integer"}}}}})
    def post(self, request):
        qs = Notification.objects.filter(user=request.user, is_read=False)
        ids = request.data.get("ids") if isinstance(request.data, dict) else None
        if ids:
            qs = qs.filter(id__in=ids)
        qs.update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)
