from django.contrib import admin

from .models import Device, TelegramLogin, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ["phone", "name", "is_specialist", "is_staff", "status", "created_at"]
    list_filter = ["status", "is_specialist", "is_staff"]
    search_fields = ["phone", "name"]
    exclude = ["password"]


admin.site.register(Device)
admin.site.register(TelegramLogin)
