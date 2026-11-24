from django.db import transaction
from rest_framework import status
from rest_framework.views import APIView

from accounts.permissions import requireAdmin
from bookings.locks import acquire_booking_schedule_lock
from bookings.models import Booking, BookingAuditLog
from bookings.serializers import AdminBookingListSerializer, AdminReassignSerializer
from bookings.services import has_overlapping_booking
from core.responses import api_response


class AdminReassignBookingView(APIView):
    """
    POST /api/admin/bookings/<id>/reassign

    Atomically cancel an APPROVED booking and approve an overlapping
    PENDING booking, recording both actions.
    """

    permission_classes = [requireAdmin]

    @transaction.atomic
    def post(self, request, booking_id: int):
        acquire_booking_schedule_lock()

        serializer = AdminReassignSerializer(data=request.data)

        if not serializer.is_valid():
            return api_response(
                status_text="error",
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        target_id = serializer.validated_data["target_booking_id"]

        if target_id == booking_id:
            return api_response(
                status_text="error",
                message="Source and target bookings must be different.",
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Lock both bookings in a consistent order.
        bookings = {
            booking.id: booking
            for booking in (
                Booking.objects.select_for_update()
                .select_related("team", "requester")
                .filter(id__in=[booking_id, target_id])
                .order_by("id")
            )
        }

        source = bookings.get(booking_id)
        target = bookings.get(target_id)

        if source is None or target is None:
            return api_response(
                status_text="error",
                message="Source or target booking not found.",
                data={},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if source.status != Booking.Status.APPROVED:
            return api_response(
                status_text="error",
                message="Source booking must be APPROVED.",
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if target.status != Booking.Status.PENDING:
            return api_response(
                status_text="error",
                message="Target booking must be PENDING.",
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if not (
            source.start_time < target.end_time
            and source.end_time > target.start_time
        ):
            return api_response(
                status_text="error",
                message="Target booking must overlap the source booking's slot.",
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # The source booking will be cancelled.
        # Every other APPROVED booking must still block overlapping requests.
        if has_overlapping_booking(
            start_time=target.start_time,
            end_time=target.end_time,
            exclude_booking_id=source.id,
            lock_rows=True,
        ):
            return api_response(
                status_text="error",
                message="Target booking conflicts with another approved booking.",
                data={},
                status_code=status.HTTP_409_CONFLICT,
            )

        reason = serializer.validated_data["reason"]
        decision_note = serializer.validated_data["decision_note"].strip()

        source.status = Booking.Status.CANCELLED
        source.decision_note = reason
        source.save(
            update_fields=["status", "decision_note", "updated_at"]
        )

        target.status = Booking.Status.APPROVED

        if decision_note:
            target.decision_note = decision_note

        target.save(
            update_fields=["status", "decision_note", "updated_at"]
        )

        BookingAuditLog.objects.create(
            booking=source,
            actor=request.user,
            action=BookingAuditLog.Action.CANCELLED,
            previous_status=Booking.Status.APPROVED,
            new_status=Booking.Status.CANCELLED,
            reason=reason,
        )

        BookingAuditLog.objects.create(
            booking=target,
            actor=request.user,
            action=BookingAuditLog.Action.APPROVED,
            previous_status=Booking.Status.PENDING,
            new_status=Booking.Status.APPROVED,
            reason=decision_note,
        )

        return api_response(
            status_text="success",
            message="Booking slot reassigned successfully.",
            data={
                "cancelled_booking": AdminBookingListSerializer(source).data,
                "approved_booking": AdminBookingListSerializer(target).data,
            },
            status_code=status.HTTP_200_OK,
        )