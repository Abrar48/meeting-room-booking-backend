from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Team, User
from bookings.models import Booking


class TeamOwnershipIntegrationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.engineering_team = Team.objects.create(
            name="Engineering Team",
        )

        cls.marketing_team = Team.objects.create(
            name="Marketing Team",
        )

        cls.admin = User.objects.create_user(
            username="seed_admin",
            email="admin@bacbon.com",
            password="Admin123!",
            role=User.Role.ADMIN,
        )

        cls.engineering_member = User.objects.create_user(
            username="member_eng",
            email="member_eng@bacbon.com",
            password="Member123!",
            role=User.Role.TEAM_MEMBER,
            team=cls.engineering_team,
        )

        cls.marketing_member = User.objects.create_user(
            username="member_mkt",
            email="member_mkt@bacbon.com",
            password="Member123!",
            role=User.Role.TEAM_MEMBER,
            team=cls.marketing_team,
        )

        cls.second_engineering_member = User.objects.create_user(
            username="member_eng_second",
            email="member_eng_second@bacbon.com",
            password="Member123!",
            role=User.Role.TEAM_MEMBER,
            team=cls.engineering_team,
        )

        start_time = timezone.now() + timedelta(days=2)
        end_time = start_time + timedelta(hours=1)

        cls.engineering_booking = Booking.objects.create(
            team=cls.engineering_team,
            requester=cls.engineering_member,
            purpose="Architecture Review Meeting",
            start_time=start_time,
            end_time=end_time,
            status=Booking.Status.PENDING,
        )

        cls.marketing_booking = Booking.objects.create(
            team=cls.marketing_team,
            requester=cls.marketing_member,
            purpose="Marketing Campaign Kickoff",
            start_time=start_time,
            end_time=end_time,
            status=Booking.Status.PENDING,
        )

    def authenticate(self, user):
        access_token = str(
            RefreshToken.for_user(user).access_token
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )

    def cancel_url(self, booking_id):
        return f"/api/bookings/{booking_id}/cancel/"

    def assert_error_response(self, response, expected_status):
        self.assertEqual(
            response.status_code,
            expected_status,
        )

        payload = response.json()

        self.assertEqual(payload["status"], "error")
        self.assertIn("data", payload)
        self.assertIn("message", payload)

    def test_engineering_member_reads_only_own_team(self):
        self.authenticate(self.engineering_member)

        response = self.client.get(
            "/api/bookings/my-requests/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        payload = response.json()
        requests = payload["data"]["requests"]

        booking_ids = {
            booking["id"] for booking in requests
        }

        self.assertIn(
            self.engineering_booking.id,
            booking_ids,
        )

        self.assertNotIn(
            self.marketing_booking.id,
            booking_ids,
        )

    def test_marketing_member_reads_only_own_team(self):
        self.authenticate(self.marketing_member)

        response = self.client.get(
            "/api/bookings/my-requests/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        payload = response.json()
        requests = payload["data"]["requests"]

        booking_ids = {
            booking["id"] for booking in requests
        }

        self.assertIn(
            self.marketing_booking.id,
            booking_ids,
        )

        self.assertNotIn(
            self.engineering_booking.id,
            booking_ids,
        )

    def test_engineering_member_cannot_cancel_marketing_booking(self):
        self.authenticate(self.engineering_member)

        response = self.client.patch(
            self.cancel_url(self.marketing_booking.id),
            {},
            format="json",
        )

        self.assert_error_response(
            response,
            status.HTTP_403_FORBIDDEN,
        )

        self.marketing_booking.refresh_from_db()

        self.assertEqual(
            self.marketing_booking.status,
            Booking.Status.PENDING,
        )

    def test_marketing_member_cannot_cancel_engineering_booking(self):
        self.authenticate(self.marketing_member)

        response = self.client.patch(
            self.cancel_url(self.engineering_booking.id),
            {},
            format="json",
        )

        self.assert_error_response(
            response,
            status.HTTP_403_FORBIDDEN,
        )

        self.engineering_booking.refresh_from_db()

        self.assertEqual(
            self.engineering_booking.status,
            Booking.Status.PENDING,
        )

    def test_member_can_cancel_own_pending_booking(self):
        self.authenticate(self.engineering_member)

        response = self.client.patch(
            self.cancel_url(self.engineering_booking.id),
            {},
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.engineering_booking.refresh_from_db()

        self.assertEqual(
            self.engineering_booking.status,
            Booking.Status.CANCELLED,
        )

    def test_same_team_member_cannot_cancel_another_members_booking(self):
        self.authenticate(self.second_engineering_member)

        response = self.client.patch(
            self.cancel_url(self.engineering_booking.id),
            {},
            format="json",
        )

        self.assert_error_response(
            response,
            status.HTTP_403_FORBIDDEN,
        )

        self.engineering_booking.refresh_from_db()

        self.assertEqual(
            self.engineering_booking.status,
            Booking.Status.PENDING,
        )

    def test_member_without_team_cannot_read_requests(self):
        self.engineering_member.team = None
        self.engineering_member.save(update_fields=["team"])

        self.authenticate(self.engineering_member)

        response = self.client.get(
            "/api/bookings/my-requests/",
        )

        self.assert_error_response(
            response,
            status.HTTP_403_FORBIDDEN,
        )

    def test_member_without_team_cannot_cancel_booking(self):
        self.engineering_member.team = None
        self.engineering_member.save(update_fields=["team"])

        self.authenticate(self.engineering_member)

        response = self.client.patch(
            self.cancel_url(self.engineering_booking.id),
            {},
            format="json",
        )

        self.assert_error_response(
            response,
            status.HTTP_403_FORBIDDEN,
        )

        self.engineering_booking.refresh_from_db()

        self.assertEqual(
            self.engineering_booking.status,
            Booking.Status.PENDING,
        )

    def test_admin_can_view_all_team_bookings(self):
        self.authenticate(self.admin)

        response = self.client.get(
            "/api/admin/bookings/",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        bookings = response.json()["data"]["bookings"]

        booking_ids = {
            booking["id"] for booking in bookings
        }

        self.assertIn(
            self.engineering_booking.id,
            booking_ids,
        )

        self.assertIn(
            self.marketing_booking.id,
            booking_ids,
        )

    def test_team_member_cannot_view_admin_bookings(self):
        self.authenticate(self.engineering_member)

        response = self.client.get(
            "/api/admin/bookings/",
        )

        self.assert_error_response(
            response,
            status.HTTP_403_FORBIDDEN,
        )

    def test_unauthenticated_user_cannot_read_requests(self):
        response = self.client.get(
            "/api/bookings/my-requests/",
        )

        self.assert_error_response(
            response,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_unauthenticated_user_cannot_cancel_booking(self):
        response = self.client.patch(
            self.cancel_url(self.engineering_booking.id),
            {},
            format="json",
        )

        self.assert_error_response(
            response,
            status.HTTP_401_UNAUTHORIZED,
        )