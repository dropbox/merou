from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.entities.permission import Permission, PermissionAccess
    from grouper.usecases.interfaces import AuditLogInterface, PermissionInterface, UserInterface
    from typing import List, Optional


class ViewPermissionUI(metaclass=ABCMeta):
    """Abstract base class for UI for ListPermissions."""

    @abstractmethod
    def viewed_permission(
        self,
        permission,  # type: Permission
        access,  # type: PermissionAccess
        audit_log_entries,  # type: List[AuditLogEntry]
    ):
        # type: (...) -> None
        pass

    @abstractmethod
    def view_permission_failed_not_found(self, name):
        # type: (str) -> None
        pass


class ViewPermission:
    """View a single permission."""

    def __init__(self, ui, permission_service, user_service, audit_log_service):
        # type: (ViewPermissionUI, PermissionInterface, UserInterface, AuditLogInterface) -> None
        self.ui = ui
        self.permission_service = permission_service
        self.user_service = user_service
        self.audit_log_service = audit_log_service

    def view_permission(self, name, actor, audit_log_limit, argument=None):
        # type: (str, str, int, Optional[str]) -> None

        permission = self.permission_service.permission(name)
        if not permission:
            self.ui.view_permission_failed_not_found(name)
            return

        audit_log = self.audit_log_service.entries_affecting_permission(name, audit_log_limit)
        access = self.user_service.permission_access_for_user(actor, name)
        self.ui.viewed_permission(permission, access, audit_log)
