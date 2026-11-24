from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Team, User
from bookings.models import Booking


class GlobalErrorHandlingTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.team = Team.objects.create(
            name="Error Handling Test Team"
        )

        self.admin = User.objects.create_user(
            username="error_test_admin",
            email="error_test_admin@example.com",
            password="TestPassword123!",
            role=User.Role.ADMIN,
        )

        self.member = User.objects.create_user(
            username="error_test_member",
            email="error_test_member@example.com",
            password="TestPassword123!",
            role=User.Role.TEAM_MEMBER,
            team=self.team,
        )

        self.start = timezone.now() + timedelta(days=5)
        self.end = self.start + timedelta(hours=1)

        self.booking = Booking.objects.create(
            team=self.team,
            requester=self.member,
            purpose="Confirmed Meeting",
            start_time=self.start,
            end_time=self.end,
            status=Booking.Status.APPROVED,
        )

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}"
        )

    def assert_error_response(self, response, expected_status):
        self.assertEqual(
            response.status_code,
            expected_status,
        )

        payload = response.json()

        self.assertEqual(
            set(payload.keys()),
            {"status", "data", "message"},
        )

        self.assertEqual(payload["status"], "error")
        self.assertIsInstance(payload["data"], dict)
        self.assertIsInstance(payload["message"], str)
        self.assertTrue(payload["message"])

    def test_400_missing_required_fields(self):
        self.authenticate(self.member)

        response = self.client.post(
            "/api/bookings/",
            {},
            format="json",
        )

        self.assert_error_response(response, 400)

    def test_400_invalid_time_range(self):
        self.authenticate(self.member)

        response = self.client.post(
            "/api/bookings/",
            {
                "purpose": "Invalid Time Range",
                "start_time": self.end.isoformat(),
                "end_time": self.start.isoformat(),
            },
            format="json",
        )

        self.assert_error_response(response, 400)

    def test_400_malformed_json(self):
        self.authenticate(self.member)

        response = self.client.post(
            "/api/bookings/",
            data='{"purpose":',
            content_type="application/json",
        )

        self.assert_error_response(response, 400)

    def test_401_missing_token(self):
        response = self.client.get(
            "/api/auth/me/"
        )

        self.assert_error_response(response, 401)

        self.assertIn(
            "WWW-Authenticate",
            response,
        )

    def test_401_invalid_token(self):
        self.client.credentials(
            HTTP_AUTHORIZATION="Bearer invalid-token"
        )

        response = self.client.get(
            "/api/auth/me/"
        )

        self.assert_error_response(response, 401)

    def test_401_invalid_login(self):
        response = self.client.post(
            "/api/auth/login/",
            {
                "username": "error_test_admin",
                "password": "WrongPassword!",
            },
            format="json",
        )

        self.assert_error_response(response, 401)

    def test_403_member_accessing_admin_endpoint(self):
        self.authenticate(self.member)

        response = self.client.get(
            "/api/admin/bookings"
        )

        self.assert_error_response(response, 403)

    def test_404_booking_not_found(self):
        self.authenticate(self.admin)

        response = self.client.patch(
            "/api/admin/bookings/999999/approve",
            {
                "decision_note": "Test missing booking."
            },
            format="json",
        )

        self.assert_error_response(response, 404)

    def test_404_unknown_api_endpoint(self):
        response = self.client.get(
            "/api/unknown-endpoint/"
        )

        self.assert_error_response(response, 404)

    def test_409_overlapping_booking(self):
        self.authenticate(self.member)

        response = self.client.post(
            "/api/bookings/",
            {
                "purpose": "Conflicting Meeting",
                "start_time": self.start.isoformat(),
                "end_time": self.end.isoformat(),
            },
            format="json",
        )

        self.assert_error_response(response, 409)

    def test_405_method_not_allowed(self):
        self.authenticate(self.admin)

        response = self.client.delete(
            "/api/admin/bookings"
        )

        self.assert_error_response(response, 405)

    def test_error_without_api_prefix(self):
        self.authenticate(self.member)

        response = self.client.get(
            "/admin/bookings"
        )

        self.assert_error_response(response, 403)

    def test_success_response_remains_unchanged(self):
        self.authenticate(self.admin)

        response = self.client.get(
            "/api/admin/bookings"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["status"],
            "success",
        )