from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Team, User
from bookings.models import Booking, BookingAuditLog
from bookings.services import has_overlapping_booking


class AdminCancelBookingTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(
            name="Cancel Test Team"
        )

        self.admin = User.objects.create_user(
            username="cancel_admin",
            email="cancel_admin@example.com",
            password="TestPassword123!",
            role=User.Role.ADMIN,
        )

        self.member = User.objects.create_user(
            username="cancel_member",
            email="cancel_member@example.com",
            password="TestPassword123!",
            role=User.Role.TEAM_MEMBER,
            team=self.team,
        )

        self.start = timezone.now() + timedelta(days=2)
        self.end = self.start + timedelta(hours=1)

        self.booking = Booking.objects.create(
            team=self.team,
            requester=self.member,
            purpose="Planning",
            start_time=self.start,
            end_time=self.end,
            status=Booking.Status.APPROVED,
        )

        self.url = (
            f"/api/admin/bookings/{self.booking.id}/admin-cancel"
        )
        self.client = APIClient()

    def test_admin_cancels_and_frees_slot_with_audit_log(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.url,
            {"reason": "Room maintenance"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")

        self.booking.refresh_from_db()

        self.assertEqual(
            self.booking.status,
            Booking.Status.CANCELLED,
        )
        self.assertEqual(
            self.booking.decision_note,
            "Room maintenance",
        )

        self.assertFalse(
            has_overlapping_booking(self.start, self.end)
        )

        log = BookingAuditLog.objects.get(
            booking=self.booking
        )

        self.assertEqual(log.actor, self.admin)
        self.assertEqual(
            log.action,
            BookingAuditLog.Action.CANCELLED,
        )
        self.assertEqual(
            log.previous_status,
            Booking.Status.APPROVED,
        )
        self.assertEqual(
            log.new_status,
            Booking.Status.CANCELLED,
        )
        self.assertEqual(log.reason, "Room maintenance")

    def test_missing_reason_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.url,
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "error")
        self.assertEqual(
            BookingAuditLog.objects.count(),
            0,
        )

    def test_blank_reason_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.url,
            {"reason": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_member_cannot_cancel(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.patch(
            self.url,
            {"reason": "Not allowed"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_cannot_cancel(self):
        response = self.client.patch(
            self.url,
            {"reason": "No token"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_repeated_cancel_is_rejected(self):
        self.client.force_authenticate(user=self.admin)

        self.client.patch(
            self.url,
            {"reason": "Maintenance"},
            format="json",
        )

        response = self.client.patch(
            self.url,
            {"reason": "Again"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            BookingAuditLog.objects.count(),
            1,
        )

    def test_pending_booking_cannot_be_admin_cancelled(self):
        self.booking.status = Booking.Status.PENDING
        self.booking.save(update_fields=["status"])

        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            self.url,
            {"reason": "Maintenance"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_nonexistent_booking_returns_404(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.patch(
            "/api/admin/bookings/999999/admin-cancel",
            {"reason": "Maintenance"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_no_api_prefix_and_trailing_slash(self):
        self.client.force_authenticate(user=self.admin)

        url = (
            f"/admin/bookings/{self.booking.id}/admin-cancel/"
        )

        response = self.client.patch(
            url,
            {"reason": "Maintenance"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)