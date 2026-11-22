from django.contrib import admin

from bookings.models import Booking, BookingAuditLog


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "purpose",
        "team",
        "requester",
        "start_time",
        "end_time",
        "status",
    )
    list_filter = ("status", "team")
    search_fields = ("purpose", "requester__username", "team__name")


@admin.register(BookingAuditLog)
class BookingAuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "booking",
        "action",
        "actor",
        "previous_status",
        "new_status",
        "created_at",
    )
    list_filter = ("action",)
    search_fields = ("booking__purpose", "actor__username", "reason")