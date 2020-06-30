from typing import TYPE_CHECKING

from grouper.constants import (
    AUDIT_MANAGER,
    PERMISSION_ADMIN,
    PERMISSION_CREATE,
    PERMISSION_GRANT,
    USER_ADMIN,
)
from grouper.entities.pagination import ListPermissionsSortKey, Pagination
from grouper.entities.permission import PermissionAccess
from grouper.usecases.interfaces import UserInterface
from grouper.util import matches_glob

if TYPE_CHECKING:
    from grouper.entities.permission_grant import GroupPermissionGrant
    from grouper.entities.user import User
    from grouper.repositories.group_edge import GroupEdgeRepository
    from grouper.repositories.interfaces import PermissionGrantRepository, PermissionRepository
    from grouper.repositories.user import UserRepository
    from grouper.usecases.authorization import Authorization
    from grouper.usecases.interfaces import AuditLogInterface
    from typing import Dict, List, Tuple


class UserService(UserInterface):
    """High-level logic to manipulate users."""

    def __init__(
        self,
        user_repository,  # type: UserRepository
        permission_repository,  # type: PermissionRepository
        permission_grant_repository,  # type: PermissionGrantRepository
        group_edge_repository,  # type: GroupEdgeRepository
        audit_log_service,  # type: AuditLogInterface
    ):
        # type: (...) -> None
        self.user_repository = user_repository
        self.permission_repository = permission_repository
        self.permission_grant_repository = permission_grant_repository
        self.group_edge_repository = group_edge_repository
        self.audit_log = audit_log_service

    def all_users(self):
        # type: () -> Dict[str, User]
        return self.user_repository.all_users()

    def disable_user(self, user, authorization):
        # type: (str, Authorization) -> None
        self.user_repository.disable_user(user)
        self.audit_log.log_disable_user(user, authorization)

    def groups_of_user(self, user):
        # type: (str) -> List[str]
        return self.group_edge_repository.groups_of_user(user)

    def permission_access_for_user(self, user, permission):
        # type: (str, str) -> PermissionAccess
        permission_admin = self.user_is_permission_admin(user)
        can_disable = permission_admin
        can_change_audited_status = permission_admin or self.user_is_audit_manager(user)
        return PermissionAccess(can_disable, can_change_audited_status)

    def permission_grants_for_user(self, user):
        # type: (str) -> List[GroupPermissionGrant]
        return self.permission_grant_repository.permission_grants_for_user(user)

    def user_exists(self, user):
        # type: (str) -> bool
        return self.user_repository.user_exists(user)

    def user_is_audit_manager(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, AUDIT_MANAGER)

    def user_is_permission_admin(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, PERMISSION_ADMIN)

    def user_is_user_admin(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, USER_ADMIN)

    def user_can_create_permissions(self, user):
        # type: (str) -> bool
        return self.permission_grant_repository.user_has_permission(user, PERMISSION_CREATE)

    def permissions_grantable_by_user(self, user):
        # type: (str) -> List[Tuple[str, str]]
        """Returns a name-sorted list of all (permission, argument glob) pairs a user can grant.

        NOTE: The list of grantable permissions is calculated based on _all_ grants of the
        PERMISSION_GRANT permission that the user has. In particular this includes indirectly
        inherited grants. As of writing, this behavior differs from the legacy non-hexagonal
        logic, so anything relying on that old logic will act differently.
        """
        pagination = Pagination(
            sort_key=ListPermissionsSortKey.NAME, reverse_sort=False, offset=0, limit=None
        )
        all_permissions = self.permission_repository.list_permissions(pagination, False).values

        if self.user_is_permission_admin(user):
            return [(p.name, "*") for p in all_permissions]

        all_grants = self.permission_grant_repository.permission_grants_for_user(user)
        grants_of_permission_grant = [g for g in all_grants if g.permission == PERMISSION_GRANT]

        result = []
        for grant in grants_of_permission_grant:
            grantable = grant.argument.split("/", 1)
            if not grantable:
                continue
            for permission in all_permissions:
                if matches_glob(grantable[0], permission.name):
                    result.append((permission.name, grantable[1] if len(grantable) > 1 else "*"))

        return result
