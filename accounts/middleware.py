from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


class TokenVerificationMiddleware:
    """
    Verifies Bearer JWT tokens on incoming requests and attaches
    the authenticated user and their team_id to the request object.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.jwt_auth = JWTAuthentication()

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
            except (InvalidToken, TokenError):
                # Invalid tokens will be handled cleanly by DRF permission classes
                pass

        return self.get_response(request)