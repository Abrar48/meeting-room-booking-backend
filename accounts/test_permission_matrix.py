from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase

from accounts.models import User
from accounts.permission_matrix import (
    ROLE_PERMISSIONS,
    Permission,
    get_role_permissions,
    has_permission,
    user_has_permission,
)


class PermissionMatrixTests(SimpleTestCase):
    def setUp(self):
        self.admin = User(
            username="matrix_admin",
            role=User.Role.ADMIN,
            is_active=True,
        )

        self.team_member = User(
            username="matrix_member",
            role=User.Role.TEAM_MEMBER,
            is_active=True,
        )

    def test_permission_enum_contains_all_required_actions(self):
        expected_permissions = {
            "approve",
            "reject",
            "reassign",
            "cancel_any",
            "cancel_own",
            "view_all",
        }

        actual_permissions = {
            permission.value for permission in Permission
        }

        self.assertEqual(
            actual_permissions,
            expected_permissions,
        )

    def test_matrix_contains_all_defined_roles(self):
        self.assertEqual(
            set(ROLE_PERMISSIONS.keys()),
            set(User.Role.values),
        )

    def test_admin_has_all_permissions(self):
        self.assertEqual(
            get_role_permissions(User.Role.ADMIN),
            frozenset(Permission),
        )

        for permission in Permission:
            with self.subTest(permission=permission):
                self.assertTrue(
                    has_permission(
                        User.Role.ADMIN,
                        permission,
                    )
                )

    def test_team_member_has_only_cancel_own_permission(self):
        self.assertEqual(
            get_role_permissions(User.Role.TEAM_MEMBER),
            frozenset({Permission.CANCEL_OWN}),
        )

    def test_team_member_can_cancel_own_booking(self):
        self.assertTrue(
            has_permission(
                User.Role.TEAM_MEMBER,
                Permission.CANCEL_OWN,
            )
        )

    def test_team_member_cannot_approve_booking(self):
        self.assertFalse(
            has_permission(
                User.Role.TEAM_MEMBER,
                Permission.APPROVE,
            )
        )

    def test_team_member_cannot_reject_booking(self):
        self.assertFalse(
            has_permission(
                User.Role.TEAM_MEMBER,
                Permission.REJECT,
            )
        )

    def test_team_member_cannot_reassign_booking(self):
        self.assertFalse(
            has_permission(
                User.Role.TEAM_MEMBER,
                Permission.REASSIGN,
            )
        )

    def test_team_member_cannot_cancel_any_booking(self):
        self.assertFalse(
            has_permission(
                User.Role.TEAM_MEMBER,
                Permission.CANCEL_ANY,
            )
        )

    def test_team_member_cannot_view_all_bookings(self):
        self.assertFalse(
            has_permission(
                User.Role.TEAM_MEMBER,
                Permission.VIEW_ALL,
            )
        )

    def test_unknown_role_has_no_permissions(self):
        self.assertEqual(
            get_role_permissions("UNKNOWN_ROLE"),
            frozenset(),
        )

        for permission in Permission:
            with self.subTest(permission=permission):
                self.assertFalse(
                    has_permission(
                        "UNKNOWN_ROLE",
                        permission,
                    )
                )

    def test_unknown_permission_is_denied(self):
        self.assertFalse(
            has_permission(
                User.Role.ADMIN,
                "delete_everything",
            )
        )

        self.assertFalse(
            has_permission(
                User.Role.TEAM_MEMBER,
                "delete_everything",
            )
        )

    def test_string_permission_values_are_supported(self):
        self.assertTrue(
            has_permission("ADMIN", "approve")
        )

        self.assertTrue(
            has_permission("TEAM_MEMBER", "cancel_own")
        )

        self.assertFalse(
            has_permission("TEAM_MEMBER", "approve")
        )

    def test_authenticated_admin_has_all_permissions(self):
        for permission in Permission:
            with self.subTest(permission=permission):
                self.assertTrue(
                    user_has_permission(
                        self.admin,
                        permission,
                    )
                )

    def test_authenticated_member_has_only_own_permission(self):
        for permission in Permission:
            with self.subTest(permission=permission):
                self.assertEqual(
                    user_has_permission(
                        self.team_member,
                        permission,
                    ),
                    permission == Permission.CANCEL_OWN,
                )

    def test_anonymous_user_has_no_permissions(self):
        user = AnonymousUser()

        for permission in Permission:
            with self.subTest(permission=permission):
                self.assertFalse(
                    user_has_permission(
                        user,
                        permission,
                    )
                )

    def test_inactive_user_has_no_permissions(self):
        self.admin.is_active = False

        for permission in Permission:
            with self.subTest(permission=permission):
                self.assertFalse(
                    user_has_permission(
                        self.admin,
                        permission,
                    )
                )

    def test_none_user_has_no_permissions(self):
        self.assertFalse(
            user_has_permission(
                None,
                Permission.APPROVE,
            )
        )

    def test_permission_matrix_is_immutable(self):
        with self.assertRaises(TypeError):
            ROLE_PERMISSIONS[User.Role.TEAM_MEMBER] = frozenset(
                Permission
            )

    def test_role_permission_sets_are_immutable(self):
        permissions = get_role_permissions(
            User.Role.TEAM_MEMBER
        )

        self.assertIsInstance(
            permissions,
            frozenset,
        )