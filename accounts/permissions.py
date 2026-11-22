from functools import wraps

from rest_framework import status
from rest_framework.permissions import BasePermission

from accounts.models import User
from core.responses import api_response


class requireAuth(BasePermission):
    """
    Server-side guard ensuring the request comes from an authenticated user.
    Returns 401 Unauthorized when unauthenticated.
    """

    message = "Authentication required."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class requireAdmin(BasePermission):
    """
    Server-side guard ensuring the authenticated user has the ADMIN role.
    Returns 401 if unauthenticated, or 403 Forbidden if role is not ADMIN.
    """

    message = "Admin privileges are required to access this resource."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.role == User.Role.ADMIN


def require_auth_decorator(view_func):
    """Function-based view guard for authenticated users (401 on failure)."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not (request.user and request.user.is_authenticated):
            return api_response(
                status_text="error",
                message="Authentication credentials were not provided or are invalid.",
                data={},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def require_admin_decorator(view_func):
    """Function-based view guard for ADMIN role (401 if unauth, 403 if not admin)."""

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not (request.user and request.user.is_authenticated):
            return api_response(
                status_text="error",
                message="Authentication credentials were not provided or are invalid.",
                data={},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        if request.user.role != User.Role.ADMIN:
            return api_response(
                status_text="error",
                message="You do not have permission to perform this action.",
                data={},
                status_code=status.HTTP_403_FORBIDDEN,
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view