from django.db import connection

BOOKING_SCHEDULE_LOCK_ID = 190001


def acquire_booking_schedule_lock() -> None:
    """Serialize schedule changes until the PostgreSQL transaction ends."""
    if not connection.in_atomic_block:
        raise RuntimeError("Booking schedule lock requires an active transaction.")

    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s)",
            [BOOKING_SCHEDULE_LOCK_ID],
        )