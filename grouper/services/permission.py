from typing import TYPE_CHECKING

from grouper.constants import SYSTEM_PERMISSIONS
from grouper.usecases.interfaces import PermissionInterface

if TYPE_CHECKING:
    from grouper.entities.pagination import PaginatedList, Pagination
    from grouper.entities.permission import Permission
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
    )
    from grouper.repositories.permission import PermissionRepository
    from grouper.repositories.permission_grant import PermissionGrantRepository
    from grouper.usecases.authorization import Authorization
    from grouper.usecases.list_permissions import ListPermissionsSortKey
    from grouper.usecases.interfaces import AuditLogInterface
    from typing import List, Optional


class PermissionService(PermissionInterface):
    """High-level logic to manipulate permissions."""

    def __init__(self, audit_log, permission_repository, permission_grant_repository):
        # type: (AuditLogInterface, PermissionRepository, PermissionGrantRepository) -> None
        self.audit_log = audit_log
        self.permission_repository = permission_repository
        self.permission_grant_repository = permission_grant_repository

    def create_permission(self, name, description=""):
        # type: (str, str) -> None
        self.permission_repository.create_permission(name, description)

    def create_system_permissions(self):
        # type: () -> None
        for name, description in SYSTEM_PERMISSIONS:
            if not self.permission_exists(name):
                self.create_permission(name, description)

    def disable_permission(self, name, authorization):
        # type: (str, Authorization) -> None
        """Disable a permission.

        An invariant for permissions is that disabled permissions are not granted to anyone.  The
        usecase is responsible for checking whether a permission is granted to any active groups or
        service accounts before calling this service method, forcing the user disabling the
        permission to remove those grants first.  However, grants to disabled groups are invisible
        (by design) and retained only to be able to re-enable the group with its previous set of
        permissions.  Semantically, it makes sense for those grants to quietly disappear without
        explicit action.

        Therefore, this service call first deletes all grants of the permission to disabled groups
        before disabling the underlying permission.

        All permission grants for a service account are deleted when that service account is
        disabled, so this issue doesn't apply for service accounts.
        """
        grants = self.permission_grant_repository.revoke_inactive_group_grants_for_permission(name)
        for grant in grants:
            self.audit_log.log_revoke_group_permission_grant(
                grant.group, grant.permission, grant.argument, authorization
            )
        self.permission_repository.disable_permission(name)
        self.audit_log.log_disable_permission(name, authorization)

    def group_grants_for_permission(self, name):
        # type: (str) -> List[GroupPermissionGrant]
        return self.permission_grant_repository.group_grants_for_permission(name)

    def service_account_grants_for_permission(self, name):
        # type: (str) -> List[ServiceAccountPermissionGrant]
        return self.permission_grant_repository.service_account_grants_for_permission(name)

    def is_system_permission(self, name):
        # type: (str) -> bool
        return name in (entry[0] for entry in SYSTEM_PERMISSIONS)

    def list_permissions(self, pagination, audited_only):
        # type: (Pagination[ListPermissionsSortKey], bool) -> PaginatedList[Permission]
        return self.permission_repository.list_permissions(pagination, audited_only)

    def permission(self, name):
        # type: (str) -> Optional[Permission]
        return self.permission_repository.get_permission(name)

    def permission_exists(self, name):
        # type: (str) -> bool
        return True if self.permission_repository.get_permission(name) else False
