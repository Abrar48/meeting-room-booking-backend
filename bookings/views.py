from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone

from django.db import transaction
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from accounts.models import User
from accounts.permissions import requireAdmin, requireAuth
from bookings.models import Booking, BookingAuditLog
from bookings.serializers import (
    AdminBookingListSerializer,
    AdminDecisionSerializer,
    AdminScheduleBookingSerializer,
    BookingCreateSerializer,
    BookingDetailSerializer,
    PublicScheduleBookingSerializer,
)
from bookings.services import (
    ensure_aware_utc,
    has_overlapping_booking,
    validate_booking_slot,
)
from core.responses import api_response


class ScheduleListView(APIView):
    """
    GET /api/bookings/schedule?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
    Returns confirmed (APPROVED) bookings overlapping the requested date range.
    Strips private notes and requester info for non-admin callers.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")

        today_utc = datetime.now(dt_timezone.utc).date()

        if start_date_str:
            start_date = parse_date(start_date_str)
            if start_date is None:
                return api_response(
                    status_text="error",
                    message="Invalid start_date format. Expected YYYY-MM-DD.",
                    data={},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        else:
            start_date = today_utc

        if end_date_str:
            end_date = parse_date(end_date_str)
            if end_date is None:
                return api_response(
                    status_text="error",
                    message="Invalid end_date format. Expected YYYY-MM-DD.",
                    data={},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
        else:
            end_date = start_date + timedelta(days=7)

        if end_date < start_date:
            return api_response(
                status_text="error",
                message="end_date cannot be earlier than start_date.",
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        range_start = datetime.combine(start_date, time.min, tzinfo=dt_timezone.utc)
        range_end = datetime.combine(
            end_date + timedelta(days=1), time.min, tzinfo=dt_timezone.utc
        )

        confirmed_bookings = (
            Booking.objects.select_related("team", "requester")
            .filter(
                status=Booking.Status.APPROVED,
                start_time__lt=range_end,
                end_time__gt=range_start,
            )
            .order_by("start_time")
        )

        active_user = (
            request.user
            if (request.user and request.user.is_authenticated)
            else getattr(request, "current_user", None)
        )
        is_admin = bool(active_user and active_user.role == User.Role.ADMIN)

        serializer_class = (
            AdminScheduleBookingSerializer
            if is_admin
            else PublicScheduleBookingSerializer
        )
        serialized_bookings = serializer_class(confirmed_bookings, many=True).data

        return api_response(
            status_text="success",
            message="Confirmed room schedule retrieved successfully.",
            data={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "count": len(serialized_bookings),
                "bookings": serialized_bookings,
            },
            status_code=status.HTTP_200_OK,
        )


class BookingListCreateView(APIView):
    """
    POST /api/bookings/
    Allows an authenticated team member to submit a new booking request.
    Validates time range and overlap against APPROVED bookings, saving as PENDING.
    """

    permission_classes = [requireAuth]

    def post(self, request):
        user = request.user

        if user.team is None:
            return api_response(
                status_text="error",
                message="You must be assigned to a team to submit a booking request.",
                data={},
                status_code=status.HTTP_403_FORBIDDEN,
            )

        serializer = BookingCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                status_text="error",
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        validated = serializer.validated_data
        requested_team_id = validated.get("team_id")

        if requested_team_id is not None and requested_team_id != user.team_id:
            return api_response(
                status_text="error",
                message="You can only submit booking requests for your own team.",
                data={},
                status_code=status.HTTP_403_FORBIDDEN,
            )

        start_utc = ensure_aware_utc(validated["start_time"])
        end_utc = ensure_aware_utc(validated["end_time"])

        validate_booking_slot(start_time=start_utc, end_time=end_utc)

        booking = Booking.objects.create(
            team=user.team,
            requester=user,
            purpose=validated["purpose"].strip(),
            start_time=start_utc,
            end_time=end_utc,
            status=Booking.Status.PENDING,
            notes=validated.get("notes", ""),
        )

        response_data = BookingDetailSerializer(booking).data
        return api_response(
            status_text="success",
            message="Booking request submitted successfully and is pending approval.",
            data={"booking": response_data},
            status_code=status.HTTP_201_CREATED,
        )


class MyTeamRequestsView(APIView):
    """
    GET /api/bookings/my-requests
    Returns all booking requests belonging strictly to the signed-in user's team,
    including status and decision_note, without exposing other teams' requests.
    """

    permission_classes = [requireAuth]

    def get(self, request):
        user = request.user

        if user.team is None:
            return api_response(
                status_text="error",
                message="You are not assigned to any team.",
                data={},
                status_code=status.HTTP_403_FORBIDDEN,
            )

        queryset = (
            Booking.objects.select_related("team", "requester")
            .filter(team=user.team)
            .order_by("-created_at")
        )

        status_param = request.query_params.get("status")
        if status_param:
            status_upper = status_param.strip().upper()
            valid_statuses = {choice[0] for choice in Booking.Status.choices}
            if status_upper not in valid_statuses:
                allowed = ", ".join(sorted(valid_statuses))
                return api_response(
                    status_text="error",
                    message=f"Invalid status filter. Allowed values: {allowed}.",
                    data={},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(status=status_upper)

        serialized_requests = BookingDetailSerializer(queryset, many=True).data

        return api_response(
            status_text="success",
            message="Team booking requests retrieved successfully.",
            data={
                "team_id": user.team.id,
                "team_name": user.team.name,
                "count": len(serialized_requests),
                "requests": serialized_requests,
            },
            status_code=status.HTTP_200_OK,
        )


class CancelOwnPendingBookingView(APIView):
    """
    PATCH /api/bookings/<id>/cancel
    Allows a team member to cancel their own booking request only if status is PENDING.
    Returns 403 if not the requester, and 400 if status is not PENDING.
    """

    permission_classes = [requireAuth]

    @transaction.atomic
    def patch(self, request, booking_id: int):
        booking = (
            Booking.objects.select_for_update()
            .select_related("team", "requester")
            .filter(id=booking_id)
            .first()
        )

        if booking is None:
            return api_response(
                status_text="error",
                message="Booking request not found.",
                data={},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if booking.requester_id != request.user.id:
            return api_response(
                status_text="error",
                message="You are only allowed to cancel your own booking requests.",
                data={},
                status_code=status.HTTP_403_FORBIDDEN,
            )

        if booking.status != Booking.Status.PENDING:
            return api_response(
                status_text="error",
                message=(
                    f"Only PENDING booking requests can be cancelled. "
                    f"Current status is {booking.status}."
                ),
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status", "updated_at"])

        response_data = BookingDetailSerializer(booking).data
        return api_response(
            status_text="success",
            message="Booking request cancelled successfully.",
            data={"booking": response_data},
            status_code=status.HTTP_200_OK,
        )


class AdminBookingListView(APIView):
    """
    GET /api/admin/bookings
    Admin-only endpoint to list all booking requests and confirmed bookings
    with optional filters for status, date range (start_date, end_date), and team.
    """

    permission_classes = [requireAdmin]

    def get(self, request):
        queryset = Booking.objects.select_related("team", "requester").order_by(
            "-created_at"
        )

        status_param = request.query_params.get("status")
        if status_param:
            status_upper = status_param.strip().upper()
            valid_statuses = {choice[0] for choice in Booking.Status.choices}
            if status_upper not in valid_statuses:
                allowed = ", ".join(sorted(valid_statuses))
                return api_response(
                    status_text="error",
                    message=f"Invalid status filter. Allowed values: {allowed}.",
                    data={},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(status=status_upper)

        team_param = request.query_params.get("team_id") or request.query_params.get(
            "team"
        )
        if team_param:
            if not team_param.isdigit():
                return api_response(
                    status_text="error",
                    message="Invalid team filter. Expected a numeric team ID.",
                    data={},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )
            queryset = queryset.filter(team_id=int(team_param))

        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        start_date = None
        end_date = None

        if start_date_str:
            start_date = parse_date(start_date_str)
            if start_date is None:
                return api_response(
                    status_text="error",
                    message="Invalid start_date format. Expected YYYY-MM-DD.",
                    data={},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_str:
            end_date = parse_date(end_date_str)
            if end_date is None:
                return api_response(
                    status_text="error",
                    message="Invalid end_date format. Expected YYYY-MM-DD.",
                    data={},
                    status_code=status.HTTP_400_BAD_REQUEST,
                )

        if start_date and end_date and end_date < start_date:
            return api_response(
                status_text="error",
                message="end_date cannot be earlier than start_date.",
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if start_date:
            range_start = datetime.combine(start_date, time.min, tzinfo=dt_timezone.utc)
            queryset = queryset.filter(end_time__gt=range_start)

        if end_date:
            range_end = datetime.combine(
                end_date + timedelta(days=1), time.min, tzinfo=dt_timezone.utc
            )
            queryset = queryset.filter(start_time__lt=range_end)

        serialized = AdminBookingListSerializer(queryset, many=True).data

        return api_response(
            status_text="success",
            message="All bookings retrieved successfully.",
            data={
                "count": len(serialized),
                "bookings": serialized,
            },
            status_code=status.HTTP_200_OK,
        )


class AdminApproveBookingView(APIView):
    """
    PATCH /api/admin/bookings/<id>/approve
    Admin-only endpoint using a DB transaction and row-level locks to re-verify
    no overlapping APPROVED booking exists, update status to APPROVED, and log audit.
    """

    permission_classes = [requireAdmin]

    @transaction.atomic
    def patch(self, request, booking_id: int):
        serializer = AdminDecisionSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                status_text="error",
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        booking = (
            Booking.objects.select_for_update()
            .select_related("team", "requester")
            .filter(id=booking_id)
            .first()
        )

        if booking is None:
            return api_response(
                status_text="error",
                message="Booking request not found.",
                data={},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if booking.status != Booking.Status.PENDING:
            return api_response(
                status_text="error",
                message=(
                    f"Only PENDING booking requests can be approved. "
                    f"Current status is {booking.status}."
                ),
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if has_overlapping_booking(
            start_time=booking.start_time,
            end_time=booking.end_time,
            exclude_booking_id=booking.id,
            lock_rows=True,
        ):
            return api_response(
                status_text="error",
                message=(
                    "Cannot approve request because it overlaps with an existing "
                    "confirmed booking."
                ),
                data={},
                status_code=status.HTTP_409_CONFLICT,
            )

        previous_status = booking.status
        decision_note = serializer.validated_data.get("decision_note", "").strip()

        booking.status = Booking.Status.APPROVED
        if decision_note:
            booking.decision_note = decision_note
        booking.save(update_fields=["status", "decision_note", "updated_at"])

        BookingAuditLog.objects.create(
            booking=booking,
            actor=request.user,
            action=BookingAuditLog.Action.APPROVED,
            previous_status=previous_status,
            new_status=Booking.Status.APPROVED,
            reason=decision_note,
        )

        response_data = AdminBookingListSerializer(booking).data
        return api_response(
            status_text="success",
            message="Booking request approved successfully.",
            data={"booking": response_data},
            status_code=status.HTTP_200_OK,
        )


class AdminRejectBookingView(APIView):
    """
    PATCH /api/admin/bookings/<id>/reject
    Admin-only endpoint to reject a PENDING booking request, store optional
    decision notes, and write an entry to BookingAuditLog.
    """

    permission_classes = [requireAdmin]

    @transaction.atomic
    def patch(self, request, booking_id: int):
        serializer = AdminDecisionSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                status_text="error",
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        booking = (
            Booking.objects.select_for_update()
            .select_related("team", "requester")
            .filter(id=booking_id)
            .first()
        )

        if booking is None:
            return api_response(
                status_text="error",
                message="Booking request not found.",
                data={},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        if booking.status != Booking.Status.PENDING:
            return api_response(
                status_text="error",
                message=(
                    f"Only PENDING booking requests can be rejected. "
                    f"Current status is {booking.status}."
                ),
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        previous_status = booking.status
        decision_note = serializer.validated_data.get("decision_note", "").strip()

        booking.status = Booking.Status.REJECTED
        if decision_note:
            booking.decision_note = decision_note
        booking.save(update_fields=["status", "decision_note", "updated_at"])

        BookingAuditLog.objects.create(
            booking=booking,
            actor=request.user,
            action=BookingAuditLog.Action.REJECTED,
            previous_status=previous_status,
            new_status=Booking.Status.REJECTED,
            reason=decision_note,
        )

        response_data = AdminBookingListSerializer(booking).data
        return api_response(
            status_text="success",
            message="Booking request rejected successfully.",
            data={"booking": response_data},
            status_code=status.HTTP_200_OK,
        )