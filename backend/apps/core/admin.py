from django.contrib import admin

from .models import AuditLog, Setting

admin.site.register(Setting)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "object_type", "object_id"]
    readonly_fields = [f.name for f in AuditLog._meta.fields]
