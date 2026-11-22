from django.contrib.auth import authenticate
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.permissions import requireAdmin, requireAuth
from accounts.serializers import LoginSerializer, UserProfileSerializer
from core.responses import api_response


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                status_text="error",
                message="Validation failed.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = authenticate(request, username=username, password=password)
        if user is None:
            return api_response(
                status_text="error",
                message="Invalid username or password.",
                data={},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

        refresh = RefreshToken.for_user(user)
        user_data = UserProfileSerializer(user).data

        return api_response(
            status_text="success",
            message="Login successful.",
            data={
                "access_token": str(refresh.access_token),
                "refresh_token": str(refresh),
                "user": user_data,
            },
            status_code=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [requireAuth]

    def get(self, request):
        user_data = UserProfileSerializer(request.user).data
        return api_response(
            status_text="success",
            message="Authenticated user details retrieved successfully.",
            data={
                "user": user_data,
                "verified_team_id": request.current_team_id,
            },
            status_code=status.HTTP_200_OK,
        )


class AdminCheckView(APIView):
    permission_classes = [requireAdmin]

    def get(self, request):
        return api_response(
            status_text="success",
            message="Admin access granted.",
            data={
                "admin_username": request.user.username,
                "role": request.user.role,
            },
            status_code=status.HTTP_200_OK,
        )