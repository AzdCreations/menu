from django.contrib import admin

from .models import Category, Membership, ScheduleException, Service, Venue, VenueHours, VenuePhoto, WorkingHours


class VenueHoursInline(admin.TabularInline):
    model = VenueHours
    extra = 0


class VenuePhotoInline(admin.TabularInline):
    model = VenuePhoto
    extra = 0


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "owner", "status", "created_at"]
    list_filter = ["status", "category"]
    search_fields = ["name", "address", "owner__phone"]
    inlines = [VenueHoursInline, VenuePhotoInline]


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0


class WorkingHoursInline(admin.TabularInline):
    model = WorkingHours
    extra = 0


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["specialist", "venue", "status", "display_name"]
    list_filter = ["status"]
    inlines = [ServiceInline, WorkingHoursInline]


admin.site.register(Category)
admin.site.register(ScheduleException)
