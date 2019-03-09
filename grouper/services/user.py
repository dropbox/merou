from typing import TYPE_CHECKING

from grouper.constants import PERMISSION_ADMIN, PERMISSION_CREATE
from grouper.usecases.interfaces import UserInterface

if TYPE_CHECKING:
    from grouper.entities.permission_grant import PermissionGrant
    from grouper.repositories.interfaces import PermissionGrantRepository
    from typing import List


class UserService(UserInterface):
    """High-level logic to manipulate users."""

    def __init__(self, permission_grant_repository):
        # type: (PermissionGrantRepository) -> None
        self.permission_grant_repository = permission_grant_repository

    def permission_grants_for_user(self, user):
        # type: (str) -> List[PermissionGrant]
        return self.permission_grant_repository.permission_grants_for_user(user)

    def user_is_permission_admin(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, PERMISSION_ADMIN)

    def user_can_create_permissions(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, PERMISSION_CREATE)
