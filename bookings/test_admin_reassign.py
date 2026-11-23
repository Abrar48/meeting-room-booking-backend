from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Team, User
from bookings.models import Booking, BookingAuditLog


class AdminReassignBookingTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(
            name="Reassign Test Team"
        )

        self.admin = User.objects.create_user(
            username="reassign_admin",
            email="reassign_admin@example.com",
            password="TestPassword123!",
            role=User.Role.ADMIN,
        )

        self.member = User.objects.create_user(
            username="reassign_member",
            email="reassign_member@example.com",
            password="TestPassword123!",
            role=User.Role.TEAM_MEMBER,
            team=self.team,
        )

        start = timezone.now() + timedelta(days=5)

        self.source = Booking.objects.create(
            team=self.team,
            requester=self.member,
            purpose="Original Meeting",
            start_time=start,
            end_time=start + timedelta(hours=1),
            status=Booking.Status.APPROVED,
        )

        self.target = Booking.objects.create(
            team=self.team,
            requester=self.member,
            purpose="Priority Meeting",
            start_time=start + timedelta(minutes=30),
            end_time=start + timedelta(hours=1, minutes=30),
            status=Booking.Status.PENDING,
        )

        self.url = f"/api/admin/bookings/{self.source.id}/reassign"

        self.payload = {
            "target_booking_id": self.target.id,
            "reason": "Priority meeting requires this slot.",
            "decision_note": "Approved through reassignment.",
        }

        self.client = APIClient()

    def test_successful_reassignment_creates_two_logs(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "success")

        self.source.refresh_from_db()
        self.target.refresh_from_db()

        self.assertEqual(
            self.source.status,
            Booking.Status.CANCELLED,
        )
        self.assertEqual(
            self.target.status,
            Booking.Status.APPROVED,
        )
        self.assertEqual(
            self.source.decision_note,
            self.payload["reason"],
        )
        self.assertEqual(
            self.target.decision_note,
            self.payload["decision_note"],
        )

        logs = BookingAuditLog.objects.all()

        self.assertEqual(logs.count(), 2)

        self.assertTrue(
            logs.filter(
                booking=self.source,
                action=BookingAuditLog.Action.CANCELLED,
                previous_status=Booking.Status.APPROVED,
                new_status=Booking.Status.CANCELLED,
                actor=self.admin,
            ).exists()
        )

        self.assertTrue(
            logs.filter(
                booking=self.target,
                action=BookingAuditLog.Action.APPROVED,
                previous_status=Booking.Status.PENDING,
                new_status=Booking.Status.APPROVED,
                actor=self.admin,
            ).exists()
        )

    def test_missing_reason_returns_400(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            "target_booking_id": self.target.id,
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "error")

    def test_same_source_and_target_returns_400(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            "target_booking_id": self.source.id,
            "reason": "Invalid reassignment.",
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_non_admin_returns_403(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_returns_401(self):
        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_nonexistent_target_returns_404(self):
        self.client.force_authenticate(user=self.admin)

        payload = {
            "target_booking_id": 999999,
            "reason": "Priority meeting.",
        }

        response = self.client.post(
            self.url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_target_must_be_pending(self):
        self.target.status = Booking.Status.REJECTED
        self.target.save(update_fields=["status"])

        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_source_must_be_approved(self):
        self.source.status = Booking.Status.CANCELLED
        self.source.save(update_fields=["status"])

        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_unrelated_slot_returns_400(self):
        self.target.start_time = (
            self.source.end_time + timedelta(hours=1)
        )
        self.target.end_time = (
            self.target.start_time + timedelta(hours=1)
        )

        self.target.save(
            update_fields=["start_time", "end_time"]
        )

        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_conflict_preserves_both_bookings(self):
        Booking.objects.create(
            team=self.team,
            requester=self.member,
            purpose="Another Confirmed Meeting",
            start_time=(
                self.target.start_time + timedelta(minutes=15)
            ),
            end_time=(
                self.target.end_time + timedelta(minutes=15)
            ),
            status=Booking.Status.APPROVED,
        )

        self.client.force_authenticate(user=self.admin)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 409)

        self.source.refresh_from_db()
        self.target.refresh_from_db()

        self.assertEqual(
            self.source.status,
            Booking.Status.APPROVED,
        )
        self.assertEqual(
            self.target.status,
            Booking.Status.PENDING,
        )
        self.assertEqual(
            BookingAuditLog.objects.count(),
            0,
        )

    def test_audit_failure_rolls_back_both_changes(self):
        self.client.force_authenticate(user=self.admin)

        with patch(
            "bookings.reassign_views.BookingAuditLog.objects.create",
            side_effect=RuntimeError("Simulated audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    self.url,
                    self.payload,
                    format="json",
                )

        self.source.refresh_from_db()
        self.target.refresh_from_db()

        self.assertEqual(
            self.source.status,
            Booking.Status.APPROVED,
        )
        self.assertEqual(
            self.target.status,
            Booking.Status.PENDING,
        )
        self.assertEqual(
            BookingAuditLog.objects.count(),
            0,
        )

    def test_without_api_prefix_and_with_slash(self):
        self.client.force_authenticate(user=self.admin)

        url = (
            f"/admin/bookings/{self.source.id}/reassign/"
        )

        response = self.client.post(
            url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)