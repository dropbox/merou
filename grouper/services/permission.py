import re
from typing import TYPE_CHECKING

from grouper.constants import ARGUMENT_VALIDATION, SYSTEM_PERMISSIONS
from grouper.usecases.interfaces import PermissionInterface

if TYPE_CHECKING:
    from grouper.entities.pagination import ListPermissionsSortKey, PaginatedList, Pagination
    from grouper.entities.permission import Permission
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
        UniqueGrantsOfPermission,
    )
    from grouper.repositories.permission import PermissionRepository
    from grouper.repositories.permission_grant import PermissionGrantRepository
    from grouper.usecases.authorization import Authorization
    from grouper.usecases.interfaces import AuditLogInterface
    from typing import Dict, List, Optional, Tuple


class PermissionService(PermissionInterface):
    """High-level logic to manipulate permissions."""

    def __init__(self, audit_log, permission_repository, permission_grant_repository):
        # type: (AuditLogInterface, PermissionRepository, PermissionGrantRepository) -> None
        self.audit_log = audit_log
        self.permission_repository = permission_repository
        self.permission_grant_repository = permission_grant_repository

    def all_grants(self):
        # type: () -> Dict[str, UniqueGrantsOfPermission]
        return self.permission_grant_repository.all_grants()

    def all_grants_of_permission(self, permission):
        # type: (str) -> UniqueGrantsOfPermission
        return self.permission_grant_repository.all_grants_of_permission(permission)

    def create_permission(self, name, description=""):
        # type: (str, str) -> None
        self.permission_repository.create_permission(name, description)

    def create_system_permissions(self):
        # type: () -> None
        for name, description in SYSTEM_PERMISSIONS:
            if not self.permission_exists(name):
                self.create_permission(name, description)

    def disable_permission_and_revoke_grants(self, name, authorization):
        # type: (str, Authorization) -> None
        """Disable a permission.

        An invariant for permissions is that disabled permissions are not granted to anyone.  The
        service therefore deletes all existing grants of that permission when disabled.  The
        usecase is responsible for checking if valid grants exist and rejecting the request or
        showing more UI prompts if disabling a permission with active grants is inappropriate.
        """
        group_grants = self.permission_grant_repository.revoke_all_group_grants(name)
        for group_grant in group_grants:
            self.audit_log.log_revoke_group_permission_grant(
                group_grant.group, group_grant.permission, group_grant.argument, authorization
            )
        service_grants = self.permission_grant_repository.revoke_all_service_account_grants(name)
        for service_grant in service_grants:
            self.audit_log.log_revoke_service_account_permission_grant(
                service_grant.service_account,
                service_grant.permission,
                service_grant.argument,
                authorization,
            )
        self.permission_repository.disable_permission(name)
        self.audit_log.log_disable_permission(name, authorization)

    def group_paginated_grants_for_permission(self, name, pagination, argument=None):
        # type: (str, Pagination, Optional[str]) -> PaginatedList[GroupPermissionGrant]
        return self.permission_grant_repository.group_paginated_grants_for_permission(
            name, pagination, argument=argument
        )

    def group_grants_for_permission(self, name, argument=None):
        # type: (str, Optional[str]) -> List[GroupPermissionGrant]
        return self.permission_grant_repository.group_grants_for_permission(
            name, argument=argument
        )

    def service_account_paginated_grants_for_permission(self, name, pagination, argument=None):
        # type: (str, Pagination, Optional[str]) -> PaginatedList[ServiceAccountPermissionGrant]
        return self.permission_grant_repository.service_account_paginated_grants_for_permission(
            name, pagination, argument=argument
        )

    def service_account_grants_for_permission(self, name, argument=None):
        # type: (str, Optional[str]) -> List[ServiceAccountPermissionGrant]
        return self.permission_grant_repository.service_account_grants_for_permission(
            name, argument=argument
        )

    def is_system_permission(self, name):
        # type: (str) -> bool
        return name in (entry[0] for entry in SYSTEM_PERMISSIONS)

    def is_valid_permission_argument(self, permission, argument):
        # type: (str, str) -> Tuple[bool, Optional[str]]
        """Check whether a permission argument is valid.

        Returns:
            Tuple of a bool (whether or not the permission argument is valid) and, if False, a
            string error message explaining why it isn't valid.
        """
        if not re.match(ARGUMENT_VALIDATION + r"$", argument):
            error = "Permission argument is not valid (does not match {})".format(
                ARGUMENT_VALIDATION
            )
            return (False, error)
        return (True, None)

    def list_permissions(self, pagination, audited_only):
        # type: (Pagination[ListPermissionsSortKey], bool) -> PaginatedList[Permission]
        return self.permission_repository.list_permissions(pagination, audited_only)

    def permission(self, name):
        # type: (str) -> Optional[Permission]
        return self.permission_repository.get_permission(name)

    def permission_exists(self, name):
        # type: (str) -> bool
        return True if self.permission_repository.get_permission(name) else False
