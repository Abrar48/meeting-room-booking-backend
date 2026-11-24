from enum import Enum
from types import MappingProxyType

from accounts.models import User


class Permission(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REASSIGN = "reassign"
    CANCEL_ANY = "cancel_any"
    CANCEL_OWN = "cancel_own"
    VIEW_ALL = "view_all"


ROLE_PERMISSIONS = MappingProxyType(
    {
        User.Role.ADMIN: frozenset(
            {
                Permission.APPROVE,
                Permission.REJECT,
                Permission.REASSIGN,
                Permission.CANCEL_ANY,
                Permission.CANCEL_OWN,
                Permission.VIEW_ALL,
            }
        ),
        User.Role.TEAM_MEMBER: frozenset(
            {
                Permission.CANCEL_OWN,
            }
        ),
    }
)


def get_role_permissions(role: str) -> frozenset[Permission]:
    """Return all permissions assigned to the given role."""
    return ROLE_PERMISSIONS.get(role, frozenset())


def has_permission(
    role: str,
    permission: Permission | str,
) -> bool:
    """Check whether a role is allowed to perform an action."""
    return permission in get_role_permissions(role)


def user_has_permission(
    user,
    permission: Permission | str,
) -> bool:
    """Check permissions for an authenticated, active user."""
    if not getattr(user, "is_authenticated", False):
        return False

    if not getattr(user, "is_active", False):
        return False

    return has_permission(
        getattr(user, "role", ""),
        permission,
    )