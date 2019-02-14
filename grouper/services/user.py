from typing import TYPE_CHECKING

from grouper.constants import PERMISSION_ADMIN, PERMISSION_CREATE
from grouper.usecases.interfaces import UserInterface

if TYPE_CHECKING:
    from grouper.repositories.interfaces import PermissionGrantRepository


class UserService(UserInterface):
    """High-level logic to manipulate users."""

    def __init__(self, permission_grant_repository):
        # type: (PermissionGrantRepository) -> None
        self.permission_grant_repository = permission_grant_repository

    def user_is_permission_admin(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, PERMISSION_ADMIN)

    def user_can_create_permissions(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, PERMISSION_CREATE)
