from typing import TYPE_CHECKING

from grouper.constants import PERMISSION_ADMIN, PERMISSION_CREATE, USER_ADMIN
from grouper.usecases.interfaces import UserInterface

if TYPE_CHECKING:
    from grouper.entities.permission_grant import PermissionGrant
    from grouper.repositories.group_edge import GroupEdgeRepository
    from grouper.repositories.interfaces import PermissionGrantRepository
    from grouper.repositories.user import UserRepository
    from grouper.services.audit_log import AuditLogService
    from grouper.usecases.authorization import Authorization
    from typing import List


class UserService(UserInterface):
    """High-level logic to manipulate users."""

    def __init__(
        self,
        user_repository,  # type: UserRepository
        permission_grant_repository,  # type: PermissionGrantRepository
        group_edge_repository,  # type: GroupEdgeRepository
        audit_log_service,  # type: AuditLogService
    ):
        # type: (...) -> None
        self.user_repository = user_repository
        self.permission_grant_repository = permission_grant_repository
        self.group_edge_repository = group_edge_repository
        self.audit_log = audit_log_service

    def disable_user(self, user, authorization):
        # type: (str, Authorization) -> None
        self.user_repository.disable_user(user)
        self.audit_log.log_disable_user(user, authorization)

    def groups_of_user(self, user):
        # type: (str) -> List[str]
        return self.group_edge_repository.groups_of_user(user)

    def permission_grants_for_user(self, user):
        # type: (str) -> List[PermissionGrant]
        return self.permission_grant_repository.permission_grants_for_user(user)

    def user_is_permission_admin(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, PERMISSION_ADMIN)

    def user_is_user_admin(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, USER_ADMIN)

    def user_can_create_permissions(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, PERMISSION_CREATE)
