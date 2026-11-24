from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.db import close_old_connections, connection, connections
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Team, User
from bookings.models import Booking, BookingAuditLog


class BookingTestMixin:
    def setUp(self):
        super().setUp()

        self.client = APIClient()

        self.engineering_team = Team.objects.create(
            name="Overlap Engineering Team"
        )

        self.marketing_team = Team.objects.create(
            name="Overlap Marketing Team"
        )

        self.admin = User.objects.create_user(
            username="overlap_admin",
            email="overlap_admin@example.com",
            password="Admin123!",
            role=User.Role.ADMIN,
        )

        self.second_admin = User.objects.create_user(
            username="overlap_admin_two",
            email="overlap_admin_two@example.com",
            password="Admin123!",
            role=User.Role.ADMIN,
        )

        self.engineering_member = User.objects.create_user(
            username="overlap_member_eng",
            email="overlap_member_eng@example.com",
            password="Member123!",
            role=User.Role.TEAM_MEMBER,
            team=self.engineering_team,
        )

        self.marketing_member = User.objects.create_user(
            username="overlap_member_mkt",
            email="overlap_member_mkt@example.com",
            password="Member123!",
            role=User.Role.TEAM_MEMBER,
            team=self.marketing_team,
        )

        self.start = (
            timezone.now() + timedelta(days=5)
        ).replace(
            hour=10,
            minute=0,
            second=0,
            microsecond=0,
        )

        self.end = self.start + timedelta(hours=1)

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def create_booking(
        self,
        member,
        start_time,
        end_time,
        booking_status=Booking.Status.PENDING,
        purpose="Task 19 Test Meeting",
    ):
        return Booking.objects.create(
            team=member.team,
            requester=member,
            purpose=purpose,
            start_time=start_time,
            end_time=end_time,
            status=booking_status,
            notes="Overlap and concurrency testing.",
        )

    def booking_payload(self, start_time, end_time):
        return {
            "purpose": "Task 19 API Test Meeting",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "notes": "Testing booking overlap.",
        }

    def approve_booking(self, booking):
        self.authenticate(self.admin)

        return self.client.patch(
            f"/api/admin/bookings/{booking.id}/approve",
            {"decision_note": "Approved for Task 19 testing."},
            format="json",
        )

    def assert_api_status(self, response, expected_status):
        self.assertEqual(
            response.status_code,
            expected_status,
            response.content,
        )

        payload = response.json()

        self.assertEqual(
            set(payload.keys()),
            {"status", "data", "message"},
        )

        expected_text = (
            "success" if expected_status < 400 else "error"
        )

        self.assertEqual(
            payload["status"],
            expected_text,
        )


class OverlapAndBookingFlowTests(
    BookingTestMixin,
    TestCase,
):
    # Exact boundary tests

    def test_exact_boundary_after_existing_booking(self):
        first = self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
            Booking.Status.APPROVED,
        )

        self.authenticate(self.marketing_member)

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(
                self.end,
                self.end + timedelta(hours=1),
            ),
            format="json",
        )

        self.assert_api_status(response, 201)

        second = Booking.objects.get(
            purpose="Task 19 API Test Meeting"
        )

        response = self.approve_booking(second)

        self.assert_api_status(response, 200)

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertEqual(
            first.status,
            Booking.Status.APPROVED,
        )

        self.assertEqual(
            second.status,
            Booking.Status.APPROVED,
        )

    def test_exact_boundary_before_existing_booking(self):
        self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
            Booking.Status.APPROVED,
        )

        self.authenticate(self.marketing_member)

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(
                self.start - timedelta(hours=1),
                self.start,
            ),
            format="json",
        )

        self.assert_api_status(response, 201)

        booking = Booking.objects.get(
            purpose="Task 19 API Test Meeting"
        )

        response = self.approve_booking(booking)

        self.assert_api_status(response, 200)

        booking.refresh_from_db()

        self.assertEqual(
            booking.status,
            Booking.Status.APPROVED,
        )

    # Overlap validation tests

    def assert_overlap_rejected(self, start_time, end_time):
        self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
            Booking.Status.APPROVED,
        )

        self.authenticate(self.marketing_member)

        initial_count = Booking.objects.count()

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(start_time, end_time),
            format="json",
        )

        self.assert_api_status(response, 409)

        self.assertEqual(
            Booking.objects.count(),
            initial_count,
        )

    def test_partial_overlap_from_left(self):
        self.assert_overlap_rejected(
            self.start - timedelta(minutes=30),
            self.start + timedelta(minutes=30),
        )

    def test_partial_overlap_from_right(self):
        self.assert_overlap_rejected(
            self.start + timedelta(minutes=30),
            self.end + timedelta(minutes=30),
        )

    def test_booking_inside_existing_slot(self):
        self.assert_overlap_rejected(
            self.start + timedelta(minutes=15),
            self.end - timedelta(minutes=15),
        )

    def test_booking_contains_existing_slot(self):
        self.assert_overlap_rejected(
            self.start - timedelta(minutes=30),
            self.end + timedelta(minutes=30),
        )

    def test_identical_time_slot_returns_409(self):
        self.assert_overlap_rejected(
            self.start,
            self.end,
        )

    def test_overlapping_pending_requests_are_allowed(self):
        self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
        )

        self.authenticate(self.marketing_member)

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(self.start, self.end),
            format="json",
        )

        self.assert_api_status(response, 201)

        self.assertEqual(
            Booking.objects.filter(
                status=Booking.Status.PENDING
            ).count(),
            2,
        )

    def test_second_overlapping_approval_returns_409(self):
        first = self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
        )

        second = self.create_booking(
            self.marketing_member,
            self.start + timedelta(minutes=30),
            self.end + timedelta(minutes=30),
        )

        response = self.approve_booking(first)

        self.assert_api_status(response, 200)

        response = self.approve_booking(second)

        self.assert_api_status(response, 409)

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertEqual(
            first.status,
            Booking.Status.APPROVED,
        )

        self.assertEqual(
            second.status,
            Booking.Status.PENDING,
        )

        self.assertEqual(
            BookingAuditLog.objects.filter(
                action=BookingAuditLog.Action.APPROVED
            ).count(),
            1,
        )

    # Cancellation tests

    def test_admin_cancellation_frees_confirmed_slot(self):
        source = self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
            Booking.Status.APPROVED,
        )

        self.authenticate(self.admin)

        response = self.client.patch(
            f"/api/admin/bookings/{source.id}/admin-cancel",
            {"reason": "Meeting room slot is no longer required."},
            format="json",
        )

        self.assert_api_status(response, 200)

        source.refresh_from_db()

        self.assertEqual(
            source.status,
            Booking.Status.CANCELLED,
        )

        self.assertTrue(
            BookingAuditLog.objects.filter(
                booking=source,
                action=BookingAuditLog.Action.CANCELLED,
                previous_status=Booking.Status.APPROVED,
                new_status=Booking.Status.CANCELLED,
            ).exists()
        )

        self.authenticate(self.marketing_member)

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(self.start, self.end),
            format="json",
        )

        self.assert_api_status(response, 201)

        replacement = Booking.objects.get(
            purpose="Task 19 API Test Meeting"
        )

        response = self.approve_booking(replacement)

        self.assert_api_status(response, 200)

        replacement.refresh_from_db()

        self.assertEqual(
            replacement.status,
            Booking.Status.APPROVED,
        )

    def test_cancelled_booking_does_not_block_slot(self):
        self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
            Booking.Status.CANCELLED,
        )

        self.authenticate(self.marketing_member)

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(self.start, self.end),
            format="json",
        )

        self.assert_api_status(response, 201)

    def test_rejected_booking_does_not_block_slot(self):
        self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
            Booking.Status.REJECTED,
        )

        self.authenticate(self.marketing_member)

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(self.start, self.end),
            format="json",
        )

        self.assert_api_status(response, 201)

    # Reassignment tests

    def test_successful_reassignment_updates_both_bookings(self):
        source = self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
            Booking.Status.APPROVED,
        )

        target = self.create_booking(
            self.marketing_member,
            self.start + timedelta(minutes=30),
            self.end + timedelta(minutes=30),
        )

        self.authenticate(self.admin)

        response = self.client.post(
            f"/api/admin/bookings/{source.id}/reassign",
            {
                "target_booking_id": target.id,
                "reason": "Priority meeting requires this slot.",
                "decision_note": "Approved through reassignment.",
            },
            format="json",
        )

        self.assert_api_status(response, 200)

        source.refresh_from_db()
        target.refresh_from_db()

        self.assertEqual(
            source.status,
            Booking.Status.CANCELLED,
        )

        self.assertEqual(
            target.status,
            Booking.Status.APPROVED,
        )

        self.assertEqual(
            BookingAuditLog.objects.count(),
            2,
        )

        self.assertTrue(
            BookingAuditLog.objects.filter(
                booking=source,
                action=BookingAuditLog.Action.CANCELLED,
            ).exists()
        )

        self.assertTrue(
            BookingAuditLog.objects.filter(
                booking=target,
                action=BookingAuditLog.Action.APPROVED,
            ).exists()
        )

    def test_reassignment_conflict_preserves_original_bookings(self):
        source = self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
            Booking.Status.APPROVED,
        )

        target = self.create_booking(
            self.marketing_member,
            self.start + timedelta(minutes=30),
            self.end + timedelta(minutes=30),
        )

        third = self.create_booking(
            self.engineering_member,
            self.end,
            self.end + timedelta(hours=1),
            Booking.Status.APPROVED,
        )

        self.authenticate(self.admin)

        response = self.client.post(
            f"/api/admin/bookings/{source.id}/reassign",
            {
                "target_booking_id": target.id,
                "reason": "Testing conflicting reassignment.",
                "decision_note": "This request must fail.",
            },
            format="json",
        )

        self.assert_api_status(response, 409)

        source.refresh_from_db()
        target.refresh_from_db()
        third.refresh_from_db()

        self.assertEqual(
            source.status,
            Booking.Status.APPROVED,
        )

        self.assertEqual(
            target.status,
            Booking.Status.PENDING,
        )

        self.assertEqual(
            third.status,
            Booking.Status.APPROVED,
        )

        self.assertEqual(
            BookingAuditLog.objects.count(),
            0,
        )


@skipUnless(
    connection.vendor == "postgresql",
    "Concurrency tests require PostgreSQL.",
)
class BookingConcurrencyTests(
    BookingTestMixin,
    TransactionTestCase,
):
    def simultaneous_approvals(self, first, second):
        barrier = Barrier(2, timeout=15)

        first_token = str(
            RefreshToken.for_user(self.admin).access_token
        )

        second_token = str(
            RefreshToken.for_user(self.second_admin).access_token
        )

        def approve_worker(booking_id, token):
            close_old_connections()

            try:
                client = APIClient()

                client.credentials(
                    HTTP_AUTHORIZATION=f"Bearer {token}"
                )

                barrier.wait()

                response = client.patch(
                    f"/api/admin/bookings/{booking_id}/approve",
                    {"decision_note": "Concurrent approval test."},
                    format="json",
                )

                return response.status_code

            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(
                approve_worker,
                first.id,
                first_token,
            )

            second_future = executor.submit(
                approve_worker,
                second.id,
                second_token,
            )

            return [
                first_future.result(timeout=30),
                second_future.result(timeout=30),
            ]

    def test_simultaneous_overlapping_approvals(self):
        first = self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
        )

        second = self.create_booking(
            self.marketing_member,
            self.start + timedelta(minutes=30),
            self.end + timedelta(minutes=30),
        )

        results = self.simultaneous_approvals(
            first,
            second,
        )

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertCountEqual(
            results,
            [200, 409],
        )

        self.assertCountEqual(
            [first.status, second.status],
            [
                Booking.Status.APPROVED,
                Booking.Status.PENDING,
            ],
        )

        self.assertEqual(
            BookingAuditLog.objects.filter(
                action=BookingAuditLog.Action.APPROVED
            ).count(),
            1,
        )

    def test_simultaneous_approval_of_same_booking(self):
        booking = self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
        )

        results = self.simultaneous_approvals(
            booking,
            booking,
        )

        booking.refresh_from_db()

        self.assertCountEqual(
            results,
            [200, 400],
        )

        self.assertEqual(
            booking.status,
            Booking.Status.APPROVED,
        )

        self.assertEqual(
            BookingAuditLog.objects.filter(
                booking=booking,
                action=BookingAuditLog.Action.APPROVED,
            ).count(),
            1,
        )

    def test_simultaneous_exact_boundary_approvals(self):
        first = self.create_booking(
            self.engineering_member,
            self.start,
            self.end,
        )

        second = self.create_booking(
            self.marketing_member,
            self.end,
            self.end + timedelta(hours=1),
        )

        results = self.simultaneous_approvals(
            first,
            second,
        )

        first.refresh_from_db()
        second.refresh_from_db()

        self.assertCountEqual(
            results,
            [200, 200],
        )

        self.assertEqual(
            first.status,
            Booking.Status.APPROVED,
        )

        self.assertEqual(
            second.status,
            Booking.Status.APPROVED,
        )

        self.assertEqual(
            BookingAuditLog.objects.filter(
                action=BookingAuditLog.Action.APPROVED
            ).count(),
            2,
        )