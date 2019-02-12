from typing import TYPE_CHECKING

from grouper.constants import PERMISSION_ADMIN, SYSTEM_PERMISSIONS
from grouper.models.user import User
from grouper.usecases.interfaces import PermissionInterface
from grouper.user_permissions import user_has_permission

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.repositories.permission import PermissionRepository
    from grouper.services.audit_log import AuditLogService
    from grouper.usecases.authorization import Authorization


class PermissionService(PermissionInterface):
    """High-level logic to manipulate permissions."""

    def __init__(self, session, audit_log, permission_repository):
        # type: (Session, AuditLogService, PermissionRepository) -> None
        self.session = session
        self.audit_log = audit_log
        self.permission_repository = permission_repository

    def disable_permission(self, name, authorization):
        # type: (str, Authorization) -> None
        self.permission_repository.disable_permission(name)
        self.audit_log.log_disable_permission(name, authorization)

    def is_system_permission(self, name):
        # type: (str) -> bool
        return name in (entry[0] for entry in SYSTEM_PERMISSIONS)

    def user_is_permission_admin(self, user_name):
        # type: (str) -> bool
        user = User.get(self.session, name=user_name)
        return user_has_permission(self.session, user, PERMISSION_ADMIN)
