from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Team, User


class AdminManagementTests(APITestCase):
    TEAMS_URL = "/api/admin/teams"
    USERS_URL = "/api/admin/users"

    @classmethod
    def setUpTestData(cls):
        cls.engineering_team = Team.objects.create(
            name="Engineering Team",
        )

        cls.marketing_team = Team.objects.create(
            name="Marketing Team",
        )

        cls.admin = User.objects.create_user(
            username="management_admin",
            email="management_admin@example.com",
            password="Admin123!",
            role=User.Role.ADMIN,
        )

        cls.member = User.objects.create_user(
            username="management_member",
            email="management_member@example.com",
            password="Member123!",
            role=User.Role.TEAM_MEMBER,
            team=cls.engineering_team,
        )

    def setUp(self):
        self.authenticate(self.admin)

    def authenticate(self, user):
        token = RefreshToken.for_user(user).access_token

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

    def user_payload(self):
        return {
            "username": "new_management_user",
            "email": "new_management_user@example.com",
            "password": "SecurePass2026!",
            "first_name": "Test",
            "last_name": "Member",
            "role": User.Role.TEAM_MEMBER,
            "team_id": self.engineering_team.id,
        }

    def assert_error(self, response, expected_status):
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

        self.assertEqual(
            payload["status"],
            "error",
        )

    def update_user(self, **fields):
        return self.client.post(
            self.USERS_URL,
            {
                "user_id": self.member.id,
                **fields,
            },
            format="json",
        )

    def test_admin_can_create_team(self):
        response = self.client.post(
            self.TEAMS_URL,
            {
                "name": "QA Team",
                "description": "Quality Assurance Team",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "success")

        self.assertTrue(
            Team.objects.filter(name="QA Team").exists()
        )

    def test_duplicate_team_name_is_rejected(self):
        response = self.client.post(
            self.TEAMS_URL,
            {"name": self.engineering_team.name},
            format="json",
        )

        self.assert_error(response, 400)

    def test_blank_team_name_is_rejected(self):
        response = self.client.post(
            self.TEAMS_URL,
            {"name": "   "},
            format="json",
        )

        self.assert_error(response, 400)

    def test_missing_team_name_is_rejected(self):
        response = self.client.post(
            self.TEAMS_URL,
            {},
            format="json",
        )

        self.assert_error(response, 400)

    def test_admin_can_create_team_member(self):
        response = self.client.post(
            self.USERS_URL,
            self.user_payload(),
            format="json",
        )

        self.assertEqual(
            response.status_code,
            201,
            response.content,
        )

        user = User.objects.get(
            username="new_management_user",
        )

        self.assertEqual(
            user.role,
            User.Role.TEAM_MEMBER,
        )

        self.assertEqual(
            user.team_id,
            self.engineering_team.id,
        )

        self.assertTrue(user.is_active)

    def test_created_password_is_hashed(self):
        payload = self.user_payload()

        response = self.client.post(
            self.USERS_URL,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        user = User.objects.get(
            username=payload["username"],
        )

        self.assertTrue(
            user.check_password(payload["password"])
        )

        self.assertNotEqual(
            user.password,
            payload["password"],
        )

    def test_password_is_not_exposed_in_response(self):
        response = self.client.post(
            self.USERS_URL,
            self.user_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        user_data = response.json()["data"]["user"]

        self.assertNotIn("password", user_data)
        self.assertNotIn("is_superuser", user_data)
        self.assertNotIn("is_staff", user_data)

    def test_duplicate_username_is_rejected(self):
        payload = self.user_payload()
        payload["username"] = self.member.username

        response = self.client.post(
            self.USERS_URL,
            payload,
            format="json",
        )

        self.assert_error(response, 400)

    def test_duplicate_email_is_rejected(self):
        payload = self.user_payload()
        payload["email"] = self.member.email

        response = self.client.post(
            self.USERS_URL,
            payload,
            format="json",
        )

        self.assert_error(response, 400)

    def test_invalid_role_is_rejected(self):
        payload = self.user_payload()
        payload["role"] = "SUPER_ADMIN"

        response = self.client.post(
            self.USERS_URL,
            payload,
            format="json",
        )

        self.assert_error(response, 400)

    def test_invalid_team_id_is_rejected(self):
        payload = self.user_payload()
        payload["team_id"] = 999999

        response = self.client.post(
            self.USERS_URL,
            payload,
            format="json",
        )

        self.assert_error(response, 400)

    def test_member_without_team_is_rejected(self):
        payload = self.user_payload()
        payload["team_id"] = None

        response = self.client.post(
            self.USERS_URL,
            payload,
            format="json",
        )

        self.assert_error(response, 400)

    def test_missing_user_fields_are_rejected(self):
        response = self.client.post(
            self.USERS_URL,
            {},
            format="json",
        )

        self.assert_error(response, 400)

    def test_admin_can_create_admin_without_team(self):
        payload = self.user_payload()
        payload["role"] = User.Role.ADMIN
        payload["team_id"] = None

        response = self.client.post(
            self.USERS_URL,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        user = User.objects.get(
            username=payload["username"],
        )

        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertIsNone(user.team_id)

    def test_admin_can_assign_user_to_another_team(self):
        response = self.update_user(
            team_id=self.marketing_team.id,
        )

        self.assertEqual(response.status_code, 200)

        self.member.refresh_from_db()

        self.assertEqual(
            self.member.team_id,
            self.marketing_team.id,
        )

    def test_admin_can_promote_member(self):
        response = self.update_user(
            role=User.Role.ADMIN,
        )

        self.assertEqual(response.status_code, 200)

        self.member.refresh_from_db()

        self.assertEqual(
            self.member.role,
            User.Role.ADMIN,
        )

    def test_admin_can_demote_another_admin(self):
        self.member.role = User.Role.ADMIN
        self.member.save(update_fields=["role"])

        response = self.update_user(
            role=User.Role.TEAM_MEMBER,
        )

        self.assertEqual(response.status_code, 200)

        self.member.refresh_from_db()

        self.assertEqual(
            self.member.role,
            User.Role.TEAM_MEMBER,
        )

    def test_admin_can_deactivate_user(self):
        response = self.update_user(
            is_active=False,
        )

        self.assertEqual(response.status_code, 200)

        self.member.refresh_from_db()

        self.assertFalse(self.member.is_active)

    def test_admin_can_reactivate_user(self):
        self.member.is_active = False
        self.member.save(update_fields=["is_active"])

        response = self.update_user(
            is_active=True,
        )

        self.assertEqual(response.status_code, 200)

        self.member.refresh_from_db()

        self.assertTrue(self.member.is_active)

    def test_deactivated_user_cannot_login(self):
        response = self.update_user(
            is_active=False,
        )

        self.assertEqual(response.status_code, 200)

        self.client.credentials()

        response = self.client.post(
            "/api/auth/login/",
            {
                "username": self.member.username,
                "password": "Member123!",
            },
            format="json",
        )

        self.assert_error(response, 401)

    def test_deactivated_user_existing_token_is_rejected(self):
        old_token = str(
            RefreshToken.for_user(self.member).access_token
        )

        response = self.update_user(
            is_active=False,
        )

        self.assertEqual(response.status_code, 200)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {old_token}",
        )

        response = self.client.get(
            "/api/auth/me/",
        )

        self.assert_error(response, 401)

    def test_admin_cannot_deactivate_own_account(self):
        response = self.client.post(
            self.USERS_URL,
            {
                "user_id": self.admin.id,
                "is_active": False,
            },
            format="json",
        )

        self.assert_error(response, 400)

        self.admin.refresh_from_db()

        self.assertTrue(self.admin.is_active)

    def test_admin_cannot_demote_own_account(self):
        response = self.client.post(
            self.USERS_URL,
            {
                "user_id": self.admin.id,
                "role": User.Role.TEAM_MEMBER,
                "team_id": self.engineering_team.id,
            },
            format="json",
        )

        self.assert_error(response, 400)

        self.admin.refresh_from_db()

        self.assertEqual(
            self.admin.role,
            User.Role.ADMIN,
        )

    def test_unknown_user_returns_404(self):
        response = self.client.post(
            self.USERS_URL,
            {
                "user_id": 999999,
                "is_active": False,
            },
            format="json",
        )

        self.assert_error(response, 404)

    def test_invalid_user_id_returns_400(self):
        response = self.client.post(
            self.USERS_URL,
            {
                "user_id": "invalid",
                "is_active": False,
            },
            format="json",
        )

        self.assert_error(response, 400)

    def test_member_cannot_create_team(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.TEAMS_URL,
            {"name": "Unauthorized Team"},
            format="json",
        )

        self.assert_error(response, 403)

        self.assertFalse(
            Team.objects.filter(
                name="Unauthorized Team",
            ).exists()
        )

    def test_member_cannot_create_user(self):
        self.authenticate(self.member)

        response = self.client.post(
            self.USERS_URL,
            self.user_payload(),
            format="json",
        )

        self.assert_error(response, 403)

    def test_member_cannot_promote_own_account(self):
        self.authenticate(self.member)

        response = self.update_user(
            role=User.Role.ADMIN,
        )

        self.assert_error(response, 403)

        self.member.refresh_from_db()

        self.assertEqual(
            self.member.role,
            User.Role.TEAM_MEMBER,
        )

    def test_unauthenticated_user_cannot_create_team(self):
        self.client.credentials()

        response = self.client.post(
            self.TEAMS_URL,
            {"name": "Unauthorized Team"},
            format="json",
        )

        self.assert_error(response, 401)

    def test_unauthenticated_user_cannot_manage_users(self):
        self.client.credentials()

        response = self.client.post(
            self.USERS_URL,
            self.user_payload(),
            format="json",
        )

        self.assert_error(response, 401)

    def test_team_endpoint_without_api_prefix(self):
        response = self.client.post(
            "/admin/teams/",
            {"name": "Prefix Test Team"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)

    def test_user_endpoint_without_api_prefix(self):
        response = self.client.post(
            "/admin/users/",
            self.user_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, 201)