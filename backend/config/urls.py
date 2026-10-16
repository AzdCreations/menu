from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts import views as accounts
from apps.bookings import views as bookings
from apps.catalog import views as catalog
from apps.core import admin_api
from apps.notifications import views as notifications

admin_router = DefaultRouter()
admin_router.register("categories", admin_api.AdminCategoryViewSet, basename="admin-category")

api = [
    # Вход
    path("auth/telegram/start", accounts.TelegramStartView.as_view()),
    path("auth/telegram/status/<str:token>", accounts.TelegramStatusView.as_view()),
    path("auth/dev-login", accounts.DevLoginView.as_view()),
    path("auth/admin-login", accounts.AdminLoginView.as_view()),
    path("auth/refresh", TokenRefreshView.as_view()),
    path("auth/logout", accounts.LogoutView.as_view()),
    path("telegram/webhook", accounts.TelegramWebhookView.as_view()),
    # Профиль
    path("me", accounts.MeView.as_view()),
    path("me/devices", accounts.DeviceView.as_view()),
    path("me/specialist", accounts.BecomeSpecialistView.as_view()),
    # Каталог
    path("categories", catalog.CategoryListView.as_view()),
    path("venues", catalog.VenueListView.as_view()),
    path("venues/<int:pk>", catalog.VenueDetailView.as_view()),
    path("specialists/<int:membership_id>/slots", catalog.SlotsView.as_view()),
    # Записи клиента
    path("bookings", bookings.BookingCreateView.as_view()),
    path("bookings/my", bookings.MyBookingsView.as_view()),
    path("bookings/<int:pk>", bookings.BookingDetailView.as_view()),
    path("bookings/<int:pk>/<str:action>", bookings.BookingActionView.as_view()),
    # Специалист и владелец
    path("pro/venues", catalog.ProVenueCreateView.as_view()),
    path("pro/venues/<int:pk>", catalog.ProVenueView.as_view()),
    path("pro/venues/<int:pk>/hours", catalog.ProVenueHoursView.as_view()),
    path("pro/venues/<int:pk>/photos", catalog.ProVenuePhotosView.as_view()),
    path("pro/venues/<int:pk>/photos/<int:photo_id>", catalog.ProVenuePhotoDeleteView.as_view()),
    path("pro/venues/<int:pk>/join", catalog.ProVenueJoinView.as_view()),
    path("pro/venues/<int:pk>/members", catalog.ProVenueMembersView.as_view()),
    path("pro/venues/<int:pk>/transfer-owner", catalog.ProTransferOwnerView.as_view()),
    path("pro/members/<int:membership_id>/<str:action>", catalog.ProMemberActionView.as_view()),
    path("pro/membership", catalog.ProMembershipView.as_view()),
    path("pro/membership/photo", catalog.ProMembershipPhotoView.as_view()),
    path("pro/membership/leave", catalog.ProMembershipLeaveView.as_view()),
    path("pro/services", catalog.ProServiceListView.as_view()),
    path("pro/services/<int:pk>", catalog.ProServiceDetailView.as_view()),
    path("pro/working-hours", catalog.ProWorkingHoursView.as_view()),
    path("pro/exceptions", catalog.ProExceptionListView.as_view()),
    path("pro/exceptions/<int:pk>", catalog.ProExceptionDetailView.as_view()),
    path("pro/bookings", bookings.ProBookingsView.as_view()),
    path("pro/bookings/manual", bookings.ProManualBookingView.as_view()),
    path("pro/blocks", bookings.ProBlockView.as_view()),
    # Уведомления
    path("notifications", notifications.NotificationListView.as_view()),
    path("notifications/read", notifications.NotificationReadView.as_view()),
    # Веб-панель админа
    path("admin/", include(admin_router.urls)),
    path("admin/venues", admin_api.AdminVenueListView.as_view()),
    path("admin/venues/<int:pk>", admin_api.AdminVenueDetailView.as_view()),
    path("admin/venues/<int:pk>/<str:action>", admin_api.AdminVenueActionView.as_view()),
    path("admin/users", admin_api.AdminUserListView.as_view()),
    path("admin/users/<int:pk>", admin_api.AdminUserDetailView.as_view()),
    path("admin/users/<int:pk>/<str:action>", admin_api.AdminUserActionView.as_view()),
    path("admin/bookings", admin_api.AdminBookingListView.as_view()),
    path("admin/stats", admin_api.AdminStatsView.as_view()),
    path("admin/settings", admin_api.AdminSettingsView.as_view()),
    path("admin/audit-log", admin_api.AdminAuditLogView.as_view()),
    # Документация
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema")),
]

urlpatterns = [
    path("health", lambda request: JsonResponse({"ok": True})),
    path("django-admin/", admin.site.urls),
    path("api/v1/", include(api)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
