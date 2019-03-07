from typing import TYPE_CHECKING

from grouper.constants import SYSTEM_PERMISSIONS
from grouper.usecases.interfaces import PermissionInterface

if TYPE_CHECKING:
    from grouper.entities.pagination import PaginatedList, Pagination
    from grouper.entities.permission import Permission
    from grouper.repositories.permission import PermissionRepository
    from grouper.services.audit_log import AuditLogService
    from grouper.usecases.authorization import Authorization
    from grouper.usecases.list_permissions import ListPermissionsSortKey


class PermissionService(PermissionInterface):
    """High-level logic to manipulate permissions."""

    def __init__(self, audit_log, permission_repository):
        # type: (AuditLogService, PermissionRepository) -> None
        self.audit_log = audit_log
        self.permission_repository = permission_repository

    def disable_permission(self, name, authorization):
        # type: (str, Authorization) -> None
        self.permission_repository.disable_permission(name)
        self.audit_log.log_disable_permission(name, authorization)

    def is_system_permission(self, name):
        # type: (str) -> bool
        return name in (entry[0] for entry in SYSTEM_PERMISSIONS)

    def list_permissions(self, pagination, audited_only):
        # type: (Pagination[ListPermissionsSortKey], bool) -> PaginatedList[Permission]
        return self.permission_repository.list_permissions(pagination, audited_only)

    def permission_exists(self, name):
        # type: (str) -> bool
        return True if self.permission_repository.get_permission(name) else False
