from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.views import APIView

from accounts.admin_serializers import (
    AdminTeamCreateSerializer,
    AdminUserIdSerializer,
    AdminUserManagementSerializer,
    AdminUserResponseSerializer,
)
from accounts.models import User
from accounts.permissions import requireAdmin
from core.responses import api_response


class AdminTeamCreateView(APIView):
    """Allow an ADMIN to create a new team."""

    permission_classes = [requireAdmin]

    def post(self, request):
        serializer = AdminTeamCreateSerializer(
            data=request.data,
        )

        if not serializer.is_valid():
            return api_response(
                status_text="error",
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                team = serializer.save()

        except IntegrityError:
            return api_response(
                status_text="error",
                message="A team with this name already exists.",
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return api_response(
            status_text="success",
            message="Team created successfully.",
            data={
                "team": AdminTeamCreateSerializer(team).data,
            },
            status_code=status.HTTP_201_CREATED,
        )


class AdminUserManagementView(APIView):
    """
    POST /api/admin/users

    Create a user when user_id is omitted.
    Update an existing user when user_id is provided.
    """

    permission_classes = [requireAdmin]

    def post(self, request):
        try:
            with transaction.atomic():
                return self.manage_user(request)

        except IntegrityError:
            return api_response(
                status_text="error",
                message="User information conflicts with an existing record.",
                data={},
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    def manage_user(self, request):
        if "user_id" not in request.data:
            return self.save_user(request)

        id_serializer = AdminUserIdSerializer(
            data=request.data,
        )

        if not id_serializer.is_valid():
            return api_response(
                status_text="error",
                message="Validation failed.",
                data=id_serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user_id = id_serializer.validated_data["user_id"]

        target_user = (
            User.objects.select_for_update()
            .filter(id=user_id)
            .first()
        )

        if target_user is None:
            return api_response(
                status_text="error",
                message="User not found.",
                data={},
                status_code=status.HTTP_404_NOT_FOUND,
            )

        return self.save_user(
            request,
            target_user,
        )

    def save_user(self, request, target_user=None):
        serializer = AdminUserManagementSerializer(
            instance=target_user,
            data=request.data,
            partial=target_user is not None,
            context={"request": request},
        )

        if not serializer.is_valid():
            return api_response(
                status_text="error",
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()

        is_created = target_user is None

        message = (
            "User created successfully."
            if is_created
            else "User updated successfully."
        )

        response_status = (
            status.HTTP_201_CREATED
            if is_created
            else status.HTTP_200_OK
        )

        return api_response(
            status_text="success",
            message=message,
            data={
                "user": AdminUserResponseSerializer(user).data,
            },
            status_code=response_status,
        )