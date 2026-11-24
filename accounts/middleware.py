from django.http import JsonResponse
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class TokenVerificationMiddleware:
    """
    Verify Bearer JWT tokens and attach user information.

    Normalize non-DRF API error responses without changing
    existing standardized responses or Django admin pages.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

    @staticmethod
    def is_api_request(request):
        path = request.path_info

        return (
            path == "/api"
            or path.startswith("/api/")
            or path.startswith("/auth/")
            or path.startswith("/bookings/")
            or path == "/admin/bookings"
            or path.startswith("/admin/bookings/")
        )

    def __call__(self, request):
        request.current_user = None
        request.current_team_id = None

        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            try:
                auth_result = self.jwt_auth.authenticate(request)

                if auth_result is not None:
                    user, _ = auth_result
                    request.current_user = user
                    request.current_team_id = user.team_id

            except (AuthenticationFailed, InvalidToken, TokenError):
                # DRF handles authentication errors.
                pass

        response = self.get_response(request)

        if not self.is_api_request(request):
            return response

        error_messages = {
            400: "Bad request.",
            401: "Authentication credentials were not provided or are invalid.",
            403: "You do not have permission to perform this action.",
            404: "Resource not found.",
            409: "Booking schedule conflict.",
        }

        if response.status_code not in error_messages:
            return response

        content_type = response.get("Content-Type", "")

        if hasattr(response, "data") or "application/json" in content_type:
            return response

        # Preserve Django admin pages under the bookings app.
        if request.path_info.startswith(
            (
                "/admin/bookings/booking/",
                "/admin/bookings/bookingauditlog/",
            )
        ):
            return response

        error_response = JsonResponse(
            {
                "status": "error",
                "data": {},
                "message": error_messages[response.status_code],
            },
            status=response.status_code,
        )

        for name, value in response.items():
            if name.lower() not in {"content-type", "content-length"}:
                error_response[name] = value

        return error_response