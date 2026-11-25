from datetime import timedelta

from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Team, User
from bookings.models import Booking
from bookings.serializers import (
    AdminScheduleBookingSerializer,
    PublicScheduleBookingSerializer,
    get_schedule_serializer_class,
)


class RoleBasedSerializerUnitTests(SimpleTestCase):
    def setUp(self):
        self.admin = User(
            username="serializer_admin",
            role=User.Role.ADMIN,
            is_active=True,
        )

        self.member = User(
            username="serializer_member",
            role=User.Role.TEAM_MEMBER,
            is_active=True,
        )

    def test_admin_uses_admin_serializer(self):
        self.assertIs(
            get_schedule_serializer_class(self.admin),
            AdminScheduleBookingSerializer,
        )

    def test_member_uses_public_serializer(self):
        self.assertIs(
            get_schedule_serializer_class(self.member),
            PublicScheduleBookingSerializer,
        )

    def test_anonymous_user_uses_public_serializer(self):
        self.assertIs(
            get_schedule_serializer_class(AnonymousUser()),
            PublicScheduleBookingSerializer,
        )

    def test_none_user_uses_public_serializer(self):
        self.assertIs(
            get_schedule_serializer_class(None),
            PublicScheduleBookingSerializer,
        )

    def test_inactive_admin_uses_public_serializer(self):
        self.admin.is_active = False

        self.assertIs(
            get_schedule_serializer_class(self.admin),
            PublicScheduleBookingSerializer,
        )

    def test_unknown_role_uses_public_serializer(self):
        self.member.role = "UNKNOWN_ROLE"

        self.assertIs(
            get_schedule_serializer_class(self.member),
            PublicScheduleBookingSerializer,
        )

    def test_staff_member_does_not_receive_admin_serializer(self):
        self.member.is_staff = True

        self.assertIs(
            get_schedule_serializer_class(self.member),
            PublicScheduleBookingSerializer,
        )

    def test_superuser_flag_does_not_bypass_role(self):
        self.member.is_superuser = True

        self.assertIs(
            get_schedule_serializer_class(self.member),
            PublicScheduleBookingSerializer,
        )


class RoleBasedSerializerIntegrationTests(APITestCase):
    PUBLIC_FIELDS = {
        "id",
        "team_id",
        "team_name",
        "purpose",
        "start_time",
        "end_time",
        "status",
    }

    PRIVATE_FIELDS = {
        "requester_id",
        "requester_username",
        "requester",
        "requester_email",
        "email",
        "first_name",
        "last_name",
        "notes",
        "decision_note",
        "admin_notes",
        "internal_notes",
    }

    ADMIN_FIELDS = PUBLIC_FIELDS | {
        "requester_id",
        "requester_username",
        "notes",
        "decision_note",
    }

    @classmethod
    def setUpTestData(cls):
        cls.engineering_team = Team.objects.create(
            name="Serializer Engineering Team",
        )

        cls.marketing_team = Team.objects.create(
            name="Serializer Marketing Team",
        )

        cls.admin = User.objects.create_user(
            username="serializer_admin",
            email="serializer_admin@example.com",
            password="Admin123!",
            role=User.Role.ADMIN,
        )

        cls.engineering_member = User.objects.create_user(
            username="serializer_member_eng",
            email="serializer_member_eng@example.com",
            password="Member123!",
            role=User.Role.TEAM_MEMBER,
            team=cls.engineering_team,
        )

        cls.marketing_member = User.objects.create_user(
            username="serializer_member_mkt",
            email="serializer_member_mkt@example.com",
            password="Member123!",
            role=User.Role.TEAM_MEMBER,
            team=cls.marketing_team,
        )

        cls.start = (
            timezone.now() + timedelta(days=5)
        ).replace(
            hour=10,
            minute=0,
            second=0,
            microsecond=0,
        )

        cls.end = cls.start + timedelta(hours=1)

        cls.engineering_booking = Booking.objects.create(
            team=cls.engineering_team,
            requester=cls.engineering_member,
            purpose="Engineering Architecture Review",
            start_time=cls.start,
            end_time=cls.end,
            status=Booking.Status.APPROVED,
            notes="PRIVATE_ENGINEERING_NOTES",
            decision_note="PRIVATE_ENGINEERING_ADMIN_NOTE",
        )

        cls.marketing_booking = Booking.objects.create(
            team=cls.marketing_team,
            requester=cls.marketing_member,
            purpose="Marketing Strategy Meeting",
            start_time=cls.end,
            end_time=cls.end + timedelta(hours=1),
            status=Booking.Status.APPROVED,
            notes="PRIVATE_MARKETING_NOTES",
            decision_note="PRIVATE_MARKETING_ADMIN_NOTE",
        )

        cls.pending_booking = Booking.objects.create(
            team=cls.engineering_team,
            requester=cls.engineering_member,
            purpose="Pending Engineering Meeting",
            start_time=cls.start,
            end_time=cls.end,
            status=Booking.Status.PENDING,
        )

        cls.cancelled_booking = Booking.objects.create(
            team=cls.marketing_team,
            requester=cls.marketing_member,
            purpose="Cancelled Marketing Meeting",
            start_time=cls.start,
            end_time=cls.end,
            status=Booking.Status.CANCELLED,
        )

        cls.rejected_booking = Booking.objects.create(
            team=cls.marketing_team,
            requester=cls.marketing_member,
            purpose="Rejected Marketing Meeting",
            start_time=cls.start,
            end_time=cls.end,
            status=Booking.Status.REJECTED,
        )

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def get_schedule(self):
        date = self.start.date().isoformat()

        return self.client.get(
            "/api/bookings/schedule/",
            {
                "start_date": date,
                "end_date": date,
            },
        )

    def get_schedule_bookings(self, response):
        self.assertEqual(
            response.status_code,
            200,
            response.content,
        )

        payload = response.json()

        self.assertEqual(
            set(payload.keys()),
            {"status", "data", "message"},
        )

        self.assertEqual(payload["status"], "success")

        bookings = payload["data"]["bookings"]

        self.assertEqual(
            payload["data"]["count"],
            len(bookings),
        )

        self.assertEqual(len(bookings), 2)

        return bookings

    def assert_public_schedule(self, response):
        bookings = self.get_schedule_bookings(response)

        for booking in bookings:
            self.assertEqual(
                set(booking.keys()),
                self.PUBLIC_FIELDS,
            )

            self.assertTrue(
                self.PRIVATE_FIELDS.isdisjoint(
                    booking.keys()
                )
            )

        return bookings

    def test_admin_receives_private_requester_fields(self):
        self.authenticate(self.admin)

        response = self.get_schedule()

        bookings = self.get_schedule_bookings(response)

        booking_map = {
            booking["id"]: booking
            for booking in bookings
        }

        engineering = booking_map[
            self.engineering_booking.id
        ]

        marketing = booking_map[
            self.marketing_booking.id
        ]

        self.assertEqual(
            engineering["requester_id"],
            self.engineering_member.id,
        )

        self.assertEqual(
            engineering["requester_username"],
            self.engineering_member.username,
        )

        self.assertEqual(
            marketing["requester_id"],
            self.marketing_member.id,
        )

        self.assertEqual(
            marketing["requester_username"],
            self.marketing_member.username,
        )

    def test_admin_receives_internal_notes(self):
        self.authenticate(self.admin)

        response = self.get_schedule()

        bookings = self.get_schedule_bookings(response)

        booking_map = {
            booking["id"]: booking
            for booking in bookings
        }

        engineering = booking_map[
            self.engineering_booking.id
        ]

        marketing = booking_map[
            self.marketing_booking.id
        ]

        self.assertEqual(
            engineering["notes"],
            "PRIVATE_ENGINEERING_NOTES",
        )

        self.assertEqual(
            engineering["decision_note"],
            "PRIVATE_ENGINEERING_ADMIN_NOTE",
        )

        self.assertEqual(
            marketing["notes"],
            "PRIVATE_MARKETING_NOTES",
        )

        self.assertEqual(
            marketing["decision_note"],
            "PRIVATE_MARKETING_ADMIN_NOTE",
        )

    def test_admin_schedule_has_expected_fields(self):
        self.authenticate(self.admin)

        response = self.get_schedule()

        bookings = self.get_schedule_bookings(response)

        for booking in bookings:
            self.assertEqual(
                set(booking.keys()),
                self.ADMIN_FIELDS,
            )

    def test_engineering_member_receives_public_fields_only(self):
        self.authenticate(self.engineering_member)

        response = self.get_schedule()

        self.assert_public_schedule(response)

    def test_marketing_member_receives_public_fields_only(self):
        self.authenticate(self.marketing_member)

        response = self.get_schedule()

        self.assert_public_schedule(response)

    def test_anonymous_user_receives_public_fields_only(self):
        response = self.get_schedule()

        self.assert_public_schedule(response)

    def test_member_cannot_see_own_private_schedule_notes(self):
        self.authenticate(self.engineering_member)

        response = self.get_schedule()

        self.assert_public_schedule(response)

        content = response.content.decode()

        self.assertNotIn(
            "PRIVATE_ENGINEERING_NOTES",
            content,
        )

        self.assertNotIn(
            "PRIVATE_ENGINEERING_ADMIN_NOTE",
            content,
        )

    def test_member_cannot_see_other_team_private_notes(self):
        self.authenticate(self.engineering_member)

        response = self.get_schedule()

        self.assert_public_schedule(response)

        content = response.content.decode()

        self.assertNotIn(
            "PRIVATE_MARKETING_NOTES",
            content,
        )

        self.assertNotIn(
            "PRIVATE_MARKETING_ADMIN_NOTE",
            content,
        )

    def test_member_cannot_see_requester_identity(self):
        self.authenticate(self.marketing_member)

        response = self.get_schedule()

        self.assert_public_schedule(response)

        content = response.content.decode()

        for user in (
            self.engineering_member,
            self.marketing_member,
        ):
            self.assertNotIn(
                user.username,
                content,
            )

            self.assertNotIn(
                user.email,
                content,
            )

    def test_member_can_see_confirmed_slots_from_both_teams(self):
        self.authenticate(self.engineering_member)

        response = self.get_schedule()

        bookings = self.assert_public_schedule(response)

        booking_ids = {
            booking["id"]
            for booking in bookings
        }

        self.assertEqual(
            booking_ids,
            {
                self.engineering_booking.id,
                self.marketing_booking.id,
            },
        )

    def test_schedule_excludes_unconfirmed_bookings(self):
        for user in (
            self.admin,
            self.engineering_member,
            self.marketing_member,
        ):
            with self.subTest(role=user.role):
                self.authenticate(user)

                response = self.get_schedule()

                bookings = self.get_schedule_bookings(
                    response
                )

                booking_ids = {
                    booking["id"]
                    for booking in bookings
                }

                self.assertNotIn(
                    self.pending_booking.id,
                    booking_ids,
                )

                self.assertNotIn(
                    self.cancelled_booking.id,
                    booking_ids,
                )

                self.assertNotIn(
                    self.rejected_booking.id,
                    booking_ids,
                )

    def test_member_cannot_override_role_using_query_parameters(self):
        self.authenticate(self.engineering_member)

        date = self.start.date().isoformat()

        response = self.client.get(
            "/api/bookings/schedule/",
            {
                "start_date": date,
                "end_date": date,
                "role": "ADMIN",
                "include_private": "true",
            },
        )

        self.assert_public_schedule(response)