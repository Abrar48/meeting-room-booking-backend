from datetime import datetime
from datetime import timezone as dt_timezone

from django.utils import timezone

from bookings.models import Booking
from core.exceptions import BookingConflictError, InvalidTimeRangeError


def ensure_aware_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware in UTC."""
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, dt_timezone.utc)
    return dt.astimezone(dt_timezone.utc)


def validate_time_range(start_time: datetime, end_time: datetime, allow_past: bool = False) -> None:
    """
    Validate that start_time and end_time form a valid future interval.
    Rejects end_time <= start_time and past start times.
    """
    start_utc = ensure_aware_utc(start_time)
    end_utc = ensure_aware_utc(end_time)

    if end_utc <= start_utc:
        raise InvalidTimeRangeError("End time must be strictly after start time.")

    if not allow_past and start_utc < timezone.now():
        raise InvalidTimeRangeError("Booking time cannot be in the past.")


def has_overlapping_booking(
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: int | None = None,
    lock_rows: bool = False,
) -> bool:
    """
    Check whether [start_time, end_time) overlaps with any APPROVED booking.
    Strict overlap condition: startA < endB AND endA > startB.
    Back-to-back boundaries (endA == startB or startA == endB) return False (allowed).
    """
    start_utc = ensure_aware_utc(start_time)
    end_utc = ensure_aware_utc(end_time)

    queryset = Booking.objects.filter(
        status=Booking.Status.APPROVED,
        start_time__lt=end_utc,
        end_time__gt=start_utc,
    )

    if exclude_booking_id is not None:
        queryset = queryset.exclude(id=exclude_booking_id)

    if lock_rows:
        queryset = queryset.select_for_update()

    return queryset.exists()


def validate_booking_slot(
    start_time: datetime,
    end_time: datetime,
    exclude_booking_id: int | None = None,
    allow_past: bool = False,
    lock_rows: bool = False,
) -> None:
    """
    Combined reusable validation helper:
    1. Rejects invalid or past time ranges.
    2. Rejects slots overlapping with confirmed (APPROVED) bookings.
    """
    validate_time_range(start_time, end_time, allow_past=allow_past)

    if has_overlapping_booking(
        start_time=start_time,
        end_time=end_time,
        exclude_booking_id=exclude_booking_id,
        lock_rows=lock_rows,
    ):
        raise BookingConflictError(
            "The requested time slot overlaps with an existing confirmed booking."
        )