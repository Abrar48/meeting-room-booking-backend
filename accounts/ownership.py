from rest_framework.exceptions import NotAuthenticated, PermissionDenied

from accounts.models import User


def requireSameTeamOrAdmin(user, team_id: int | None) -> None:
    """Allow admins or authenticated members of the requested team."""
    if not getattr(user, "is_authenticated", False):
        raise NotAuthenticated(
            "Authentication credentials were not provided."
        )

    if not getattr(user, "is_active", False):
        raise PermissionDenied(
            "Your account is inactive."
        )

    if user.role == User.Role.ADMIN:
        return

    if user.role != User.Role.TEAM_MEMBER:
        raise PermissionDenied(
            "You do not have permission to perform this action."
        )

    if user.team_id is None:
        raise PermissionDenied(
            "You are not assigned to any team."
        )

    if team_id is None or user.team_id != team_id:
        raise PermissionDenied(
            "You are only allowed to access your own team's bookings."
        )