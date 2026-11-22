from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import Team, User
from bookings.models import Booking
from bookings.services import has_overlapping_booking, validate_booking_slot
from core.exceptions import BookingConflictError, InvalidTimeRangeError


class TimeAndOverlapValidationTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Engineering")
        self.user = User.objects.create_user(
            username="tester",
            email="tester@bacbon.com",
            password="Password123!",
            role=User.Role.TEAM_MEMBER,
            team=self.team,
        )
        # Base future window: tomorrow from 10:00 UTC to 11:00 UTC
        tomorrow = timezone.now() + timedelta(days=1)
        self.base_start = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        self.base_end = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)

        # Create one APPROVED booking from 10:00 to 11:00
        self.confirmed_booking = Booking.objects.create(
            team=self.team,
            requester=self.user,
            purpose="Confirmed Standup",
            start_time=self.base_start,
            end_time=self.base_end,
            status=Booking.Status.APPROVED,
        )

    def test_rejects_past_start_time(self):
        past_start = timezone.now() - timedelta(hours=2)
        past_end = timezone.now() - timedelta(hours=1)
        with self.assertRaises(InvalidTimeRangeError):
            validate_booking_slot(past_start, past_end)

    def test_rejects_end_time_equal_to_start_time(self):
        with self.assertRaises(InvalidTimeRangeError):
            validate_booking_slot(self.base_end, self.base_end)

    def test_rejects_end_time_before_start_time(self):
        with self.assertRaises(InvalidTimeRangeError):
            validate_booking_slot(self.base_end, self.base_start)

    def test_detects_overlapping_booking(self):
        # 10:30 to 11:30 overlaps with 10:00 to 11:00
        overlap_start = self.base_start + timedelta(minutes=30)
        overlap_end = self.base_end + timedelta(minutes=30)
        self.assertTrue(has_overlapping_booking(overlap_start, overlap_end))
        with self.assertRaises(BookingConflictError):
            validate_booking_slot(overlap_start, overlap_end)

    def test_allows_back_to_back_boundary_after(self):
        # 11:00 to 12:00 starts exactly when 10:00-11:00 ends (endA == startB)
        next_start = self.base_end
        next_end = self.base_end + timedelta(hours=1)
        self.assertFalse(has_overlapping_booking(next_start, next_end))
        validate_booking_slot(next_start, next_end)  # Should not raise

    def test_allows_back_to_back_boundary_before(self):
        # 09:00 to 10:00 ends exactly when 10:00-11:00 starts
        prev_start = self.base_start - timedelta(hours=1)
        prev_end = self.base_start
        self.assertFalse(has_overlapping_booking(prev_start, prev_end))
        validate_booking_slot(prev_start, prev_end)  # Should not raise

    def test_pending_booking_does_not_block_slot(self):
        # Create a PENDING booking from 14:00 to 15:00
        pending_start = self.base_start.replace(hour=14)
        pending_end = self.base_start.replace(hour=15)
        Booking.objects.create(
            team=self.team,
            requester=self.user,
            purpose="Pending Sync",
            start_time=pending_start,
            end_time=pending_end,
            status=Booking.Status.PENDING,
        )
        # Another request for 14:00-15:00 should not conflict with PENDING
        self.assertFalse(has_overlapping_booking(pending_start, pending_end))