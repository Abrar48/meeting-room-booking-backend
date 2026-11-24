from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Team, User
from bookings.models import Booking


class AuthRBACValidationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.engineering_team = Team.objects.create(
            name="Test Engineering Team"
        )

        self.marketing_team = Team.objects.create(
            name="Test Marketing Team"
        )

        self.admin = User.objects.create_user(
            username="rbac_admin",
            email="rbac_admin@example.com",
            password="Admin123!",
            role=User.Role.ADMIN,
        )

        self.engineering_member = User.objects.create_user(
            username="rbac_member_eng",
            email="rbac_member_eng@example.com",
            password="Member123!",
            role=User.Role.TEAM_MEMBER,
            team=self.engineering_team,
        )

        self.marketing_member = User.objects.create_user(
            username="rbac_member_mkt",
            email="rbac_member_mkt@example.com",
            password="Member123!",
            role=User.Role.TEAM_MEMBER,
            team=self.marketing_team,
        )

        self.start = timezone.now() + timedelta(days=5)
        self.end = self.start + timedelta(hours=1)

        self.engineering_booking = Booking.objects.create(
            team=self.engineering_team,
            requester=self.engineering_member,
            purpose="Engineering Planning Meeting",
            start_time=self.start,
            end_time=self.end,
            status=Booking.Status.PENDING,
            notes="Engineering private notes",
        )

        self.marketing_booking = Booking.objects.create(
            team=self.marketing_team,
            requester=self.marketing_member,
            purpose="Marketing Campaign Meeting",
            start_time=self.start + timedelta(hours=2),
            end_time=self.end + timedelta(hours=2),
            status=Booking.Status.PENDING,
            notes="Marketing private notes",
        )

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def assert_error_response(self, response, expected_status):
        self.assertEqual(response.status_code, expected_status)

        payload = response.json()

        self.assertEqual(
            set(payload.keys()),
            {"status", "data", "message"},
        )

        self.assertEqual(payload["status"], "error")
        self.assertIsInstance(payload["data"], dict)
        self.assertTrue(payload["message"])

    def booking_payload(self, start_time, end_time):
        return {
            "purpose": "Task 18 Validation Test Meeting",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "notes": "Integration testing.",
        }

    # Authentication tests

    def test_valid_login_returns_success(self):
        response = self.client.post(
            "/api/auth/login/",
            {
                "username": "rbac_member_eng",
                "password": "Member123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        data = response.json()["data"]
        token = data.get("access") or data.get("access_token")

        self.assertTrue(token)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

        profile_response = self.client.get("/api/auth/me/")

        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(
            profile_response.json()["status"],
            "success",
        )

    def test_invalid_login_returns_401(self):
        response = self.client.post(
            "/api/auth/login/",
            {
                "username": "rbac_member_eng",
                "password": "WrongPassword!",
            },
            format="json",
        )

        self.assert_error_response(response, 401)

    def test_missing_token_returns_401(self):
        response = self.client.get(
            "/api/bookings/my-requests"
        )

        self.assert_error_response(response, 401)

    def test_invalid_token_returns_401(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Bearer invalid-test-token"
        )

        response = self.client.get(
            "/api/bookings/my-requests"
        )

        self.assert_error_response(response, 401)

    # Role-based access control tests

    def test_member_cannot_access_admin_booking_list(self):
        self.authenticate(self.engineering_member)

        response = self.client.get(
            "/api/admin/bookings"
        )

        self.assert_error_response(response, 403)

    def test_member_cannot_approve_booking(self):
        self.authenticate(self.engineering_member)

        url = (
            f"/api/admin/bookings/"
            f"{self.engineering_booking.id}/approve"
        )

        response = self.client.patch(
            url,
            {"decision_note": "Unauthorized approval."},
            format="json",
        )

        self.assert_error_response(response, 403)

        self.engineering_booking.refresh_from_db()

        self.assertEqual(
            self.engineering_booking.status,
            Booking.Status.PENDING,
        )

    def test_member_cannot_reject_booking(self):
        self.authenticate(self.engineering_member)

        url = (
            f"/api/admin/bookings/"
            f"{self.engineering_booking.id}/reject"
        )

        response = self.client.patch(
            url,
            {"decision_note": "Unauthorized rejection."},
            format="json",
        )

        self.assert_error_response(response, 403)

        self.engineering_booking.refresh_from_db()

        self.assertEqual(
            self.engineering_booking.status,
            Booking.Status.PENDING,
        )

    def test_member_cannot_admin_cancel_booking(self):
        self.engineering_booking.status = Booking.Status.APPROVED

        self.engineering_booking.save(
            update_fields=["status"]
        )

        self.authenticate(self.engineering_member)

        url = (
            f"/api/admin/bookings/"
            f"{self.engineering_booking.id}/admin-cancel"
        )

        response = self.client.patch(
            url,
            {"reason": "Unauthorized admin cancellation."},
            format="json",
        )

        self.assert_error_response(response, 403)

        self.engineering_booking.refresh_from_db()

        self.assertEqual(
            self.engineering_booking.status,
            Booking.Status.APPROVED,
        )

    def test_member_cannot_reassign_booking(self):
        self.engineering_booking.status = Booking.Status.APPROVED

        self.engineering_booking.save(
            update_fields=["status"]
        )

        self.marketing_booking.start_time = self.start
        self.marketing_booking.end_time = self.end

        self.marketing_booking.save(
            update_fields=["start_time", "end_time"]
        )

        self.authenticate(self.engineering_member)

        url = (
            f"/api/admin/bookings/"
            f"{self.engineering_booking.id}/reassign"
        )

        response = self.client.post(
            url,
            {
                "target_booking_id": self.marketing_booking.id,
                "reason": "Unauthorized reassignment.",
            },
            format="json",
        )

        self.assert_error_response(response, 403)

        self.engineering_booking.refresh_from_db()
        self.marketing_booking.refresh_from_db()

        self.assertEqual(
            self.engineering_booking.status,
            Booking.Status.APPROVED,
        )

        self.assertEqual(
            self.marketing_booking.status,
            Booking.Status.PENDING,
        )

    def test_admin_can_access_admin_booking_list(self):
        self.authenticate(self.admin)

        response = self.client.get(
            "/api/admin/bookings"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    # Cross-team isolation tests

    def test_engineering_member_sees_only_own_team_requests(self):
        self.authenticate(self.engineering_member)

        response = self.client.get(
            "/api/bookings/my-requests"
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertEqual(payload["status"], "success")

        bookings = payload["data"]["requests"]

        booking_ids = {
            booking["id"] for booking in bookings
        }

        self.assertEqual(
            booking_ids,
            {self.engineering_booking.id},
        )

        self.assertNotIn(
            self.marketing_booking.id,
            booking_ids,
        )

    def test_marketing_member_sees_only_own_team_requests(self):
        self.authenticate(self.marketing_member)

        response = self.client.get(
            "/api/bookings/my-requests"
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertEqual(payload["status"], "success")

        bookings = payload["data"]["requests"]

        booking_ids = {
            booking["id"] for booking in bookings
        }

        self.assertEqual(
            booking_ids,
            {self.marketing_booking.id},
        )

        self.assertNotIn(
            self.engineering_booking.id,
            booking_ids,
        )

    def test_member_cannot_cancel_other_team_booking(self):
        self.authenticate(self.marketing_member)

        url = (
            f"/api/bookings/"
            f"{self.engineering_booking.id}/cancel/"
        )

        response = self.client.patch(
            url,
            {},
            format="json",
        )

        self.assert_error_response(response, 403)

        self.engineering_booking.refresh_from_db()

        self.assertEqual(
            self.engineering_booking.status,
            Booking.Status.PENDING,
        )

    def test_member_can_cancel_own_pending_booking(self):
        self.authenticate(self.engineering_member)

        url = (
            f"/api/bookings/"
            f"{self.engineering_booking.id}/cancel/"
        )

        response = self.client.patch(
            url,
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

        self.engineering_booking.refresh_from_db()

        self.assertEqual(
            self.engineering_booking.status,
            Booking.Status.CANCELLED,
        )

    # Booking validation tests

    def test_end_before_start_returns_400(self):
        self.authenticate(self.engineering_member)

        initial_count = Booking.objects.count()

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(self.end, self.start),
            format="json",
        )

        self.assert_error_response(response, 400)

        self.assertEqual(
            Booking.objects.count(),
            initial_count,
        )

    def test_equal_start_and_end_returns_400(self):
        self.authenticate(self.engineering_member)

        initial_count = Booking.objects.count()

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(self.start, self.start),
            format="json",
        )

        self.assert_error_response(response, 400)

        self.assertEqual(
            Booking.objects.count(),
            initial_count,
        )

    def test_past_time_range_returns_400(self):
        self.authenticate(self.engineering_member)

        initial_count = Booking.objects.count()

        past_start = timezone.now() - timedelta(days=2)
        past_end = past_start + timedelta(hours=1)

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(past_start, past_end),
            format="json",
        )

        self.assert_error_response(response, 400)

        self.assertEqual(
            Booking.objects.count(),
            initial_count,
        )

    def test_missing_required_fields_returns_400(self):
        self.authenticate(self.engineering_member)

        initial_count = Booking.objects.count()

        response = self.client.post(
            "/api/bookings/",
            {},
            format="json",
        )

        self.assert_error_response(response, 400)

        self.assertEqual(
            Booking.objects.count(),
            initial_count,
        )

    def test_approved_booking_overlap_returns_409(self):
        self.engineering_booking.status = Booking.Status.APPROVED

        self.engineering_booking.save(
            update_fields=["status"]
        )

        self.authenticate(self.marketing_member)

        initial_count = Booking.objects.count()

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(self.start, self.end),
            format="json",
        )

        self.assert_error_response(response, 409)

        self.assertEqual(
            Booking.objects.count(),
            initial_count,
        )

    def test_valid_future_booking_returns_201(self):
        self.authenticate(self.engineering_member)

        initial_count = Booking.objects.count()

        valid_start = self.start + timedelta(days=2)
        valid_end = valid_start + timedelta(hours=1)

        response = self.client.post(
            "/api/bookings/",
            self.booking_payload(valid_start, valid_end),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "success")

        self.assertEqual(
            Booking.objects.count(),
            initial_count + 1,
        )

        booking = Booking.objects.get(
            purpose="Task 18 Validation Test Meeting"
        )

        self.assertEqual(
            booking.status,
            Booking.Status.PENDING,
        )

        self.assertEqual(
            booking.team_id,
            self.engineering_team.id,
        )

        self.assertEqual(
            booking.requester_id,
            self.engineering_member.id,
        )