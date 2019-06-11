from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from six import with_metaclass

if TYPE_CHECKING:
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.entities.permission import Permission, PermissionAccess
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
    )
    from grouper.usecases.interfaces import AuditLogInterface, PermissionInterface, UserInterface
    from typing import List


class ViewPermissionUI(with_metaclass(ABCMeta, object)):
    """Abstract base class for UI for ListPermissions."""

    @abstractmethod
    def viewed_permission(
        self,
        permission,  # type: Permission
        group_grants,  # type: List[GroupPermissionGrant]
        service_account_grants,  # type: List[ServiceAccountPermissionGrant]
        access,  # type: PermissionAccess
        audit_log_entries,  # type: List[AuditLogEntry]
    ):
        # type: (...) -> None
        pass

    @abstractmethod
    def view_permission_failed_not_found(self, name):
        # type: (str) -> None
        pass


class ViewPermission(object):
    """View a single permission."""

    def __init__(self, ui, permission_service, user_service, audit_log_service):
        # type: (ViewPermissionUI, PermissionInterface, UserInterface, AuditLogInterface) -> None
        self.ui = ui
        self.permission_service = permission_service
        self.user_service = user_service
        self.audit_log_service = audit_log_service

    def view_permission(self, name, actor, audit_log_limit):
        # type: (str, str, int) -> None
        permission = self.permission_service.permission(name)
        if not permission:
            self.ui.view_permission_failed_not_found(name)
            return
        group_grants = self.permission_service.group_grants_for_permission(name)
        service_grants = self.permission_service.service_account_grants_for_permission(name)
        audit_log = self.audit_log_service.entries_affecting_permission(name, audit_log_limit)
        access = self.user_service.permission_access_for_user(actor, name)
        self.ui.viewed_permission(permission, group_grants, service_grants, access, audit_log)
