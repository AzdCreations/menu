from django.contrib import admin

from .models import Booking, BookingEvent


class BookingEventInline(admin.TabularInline):
    model = BookingEvent
    extra = 0
    readonly_fields = ["old_status", "new_status", "actor", "reason", "created_at"]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "start", "venue", "specialist", "client", "status", "kind"]
    list_filter = ["status", "kind", "source"]
    inlines = [BookingEventInline]
