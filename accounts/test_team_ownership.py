from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase
from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from accounts.models import User
from accounts.ownership import requireSameTeamOrAdmin


class TeamOwnershipGuardTests(SimpleTestCase):
    def setUp(self):
        self.admin = User(
            username="ownership_admin",
            role=User.Role.ADMIN,
            is_active=True,
        )

        self.engineering_member = User(
            username="ownership_member_eng",
            role=User.Role.TEAM_MEMBER,
            team_id=3,
            is_active=True,
        )

        self.marketing_member = User(
            username="ownership_member_mkt",
            role=User.Role.TEAM_MEMBER,
            team_id=4,
            is_active=True,
        )

    def assert_permission_denied(self, user, team_id):
        with self.assertRaises(PermissionDenied) as context:
            requireSameTeamOrAdmin(user, team_id)

        self.assertEqual(
            context.exception.status_code,
            403,
        )

    def test_admin_can_access_engineering_team(self):
        self.assertIsNone(
            requireSameTeamOrAdmin(self.admin, 3)
        )

    def test_admin_can_access_marketing_team(self):
        self.assertIsNone(
            requireSameTeamOrAdmin(self.admin, 4)
        )

    def test_admin_without_team_can_access_any_team(self):
        self.admin.team_id = None

        self.assertIsNone(
            requireSameTeamOrAdmin(self.admin, 3)
        )

        self.assertIsNone(
            requireSameTeamOrAdmin(self.admin, 4)
        )

    def test_engineering_member_can_access_own_team(self):
        self.assertIsNone(
            requireSameTeamOrAdmin(
                self.engineering_member,
                3,
            )
        )

    def test_marketing_member_can_access_own_team(self):
        self.assertIsNone(
            requireSameTeamOrAdmin(
                self.marketing_member,
                4,
            )
        )

    def test_engineering_member_cannot_access_marketing_team(self):
        self.assert_permission_denied(
            self.engineering_member,
            4,
        )

    def test_marketing_member_cannot_access_engineering_team(self):
        self.assert_permission_denied(
            self.marketing_member,
            3,
        )

    def test_member_cannot_access_unknown_team(self):
        self.assert_permission_denied(
            self.engineering_member,
            999,
        )

    def test_member_without_team_is_denied(self):
        self.engineering_member.team_id = None

        self.assert_permission_denied(
            self.engineering_member,
            3,
        )

    def test_member_cannot_access_booking_without_team(self):
        self.assert_permission_denied(
            self.engineering_member,
            None,
        )

    def test_missing_team_ids_do_not_grant_access(self):
        self.engineering_member.team_id = None

        self.assert_permission_denied(
            self.engineering_member,
            None,
        )

    def test_anonymous_user_is_unauthorized(self):
        with self.assertRaises(NotAuthenticated) as context:
            requireSameTeamOrAdmin(
                AnonymousUser(),
                3,
            )

        self.assertEqual(
            context.exception.status_code,
            401,
        )

    def test_none_user_is_unauthorized(self):
        with self.assertRaises(NotAuthenticated) as context:
            requireSameTeamOrAdmin(None, 3)

        self.assertEqual(
            context.exception.status_code,
            401,
        )

    def test_inactive_admin_is_denied(self):
        self.admin.is_active = False

        self.assert_permission_denied(
            self.admin,
            3,
        )

    def test_inactive_member_is_denied(self):
        self.engineering_member.is_active = False

        self.assert_permission_denied(
            self.engineering_member,
            3,
        )

    def test_unknown_role_is_denied(self):
        self.engineering_member.role = "UNKNOWN_ROLE"

        self.assert_permission_denied(
            self.engineering_member,
            3,
        )

    def test_staff_flag_does_not_bypass_team_ownership(self):
        self.engineering_member.is_staff = True

        self.assert_permission_denied(
            self.engineering_member,
            4,
        )

    def test_superuser_flag_does_not_bypass_team_ownership(self):
        self.engineering_member.is_superuser = True

        self.assert_permission_denied(
            self.engineering_member,
            4,
        )