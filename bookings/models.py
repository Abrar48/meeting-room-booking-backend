from django.conf import settings
from django.db import models

from accounts.models import Team


class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="booking_requests",
    )
    purpose = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    notes = models.TextField(blank=True, default="")
    decision_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bookings"
        ordering = ["start_time"]
        indexes = [
            models.Index(fields=["status", "start_time", "end_time"]),
        ]

    def __str__(self):
        return f"{self.purpose} - {self.team.name} ({self.status})"


class BookingAuditLog(models.Model):
    class Action(models.TextChoices):
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        REASSIGNED = "REASSIGNED", "Reassigned"

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="performed_booking_actions",
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    previous_status = models.CharField(
        max_length=20,
        choices=Booking.Status.choices,
        blank=True,
        default="",
    )
    new_status = models.CharField(
        max_length=20,
        choices=Booking.Status.choices,
    )
    reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "booking_audit_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Booking #{self.booking_id} - {self.action}"