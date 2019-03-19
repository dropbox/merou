from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import desc

from grouper.entities.audit_log_entry import AuditLogEntry
from grouper.entities.group import GroupNotFoundException
from grouper.entities.permission import PermissionNotFoundException
from grouper.entities.user import UserNotFoundException
from grouper.models.audit_log import AuditLog, AuditLogCategory
from grouper.models.group import Group
from grouper.models.permission import Permission
from grouper.models.user import User
from grouper.plugin import get_plugin_proxy

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.usecases.authorization import Authorization
    from typing import List, Optional


class AuditLogRepository(object):
    """SQL storage layer for audit log entries."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def get_entries_affecting_permission(self, permission):
        # type: (str) -> List[AuditLogEntry]
        permission_obj = Permission.get(self.session, name=permission)
        if not permission_obj:
            return []
        results = (
            self.session.query(AuditLog)
            .filter(AuditLog.on_permission_id == permission_obj.id)
            .order_by(desc(AuditLog.log_time))
        )
        return [self._to_audit_log_entry(e) for e in results]

    def log(
        self,
        authorization,  # type: Authorization
        action,  # type: str
        description,  # type: str
        on_user=None,  # type: Optional[str]
        on_group=None,  # type: Optional[str]
        on_permission=None,  # type: Optional[str]
        category=AuditLogCategory.general,  # type: AuditLogCategory
    ):
        # type: (...) -> None
        """Log an action to the audit log.

        Arguments don't cover all use cases yet.  This method will be expanded as further use cases
        are ported to this service.
        """
        actor = self._id_for_user(authorization.actor)

        # We currently have no way to log audit log entries for objects that no longer exist.  This
        # should eventually be fixed via a schema change to use strings for all fields of the audit
        # log.  For now, we'll die with an exception.
        user = self._id_for_user(on_user) if on_user else None
        group = self._id_for_group(on_group) if on_group else None
        permission = self._id_for_permission(on_permission) if on_permission else None

        entry = AuditLog(
            actor_id=actor,
            log_time=datetime.utcnow(),
            action=action,
            description=description,
            on_user_id=user,
            on_group_id=group,
            on_permission_id=permission,
            category=int(category),
        )
        entry.add(self.session)

        # This should happen at the service layer, not the repository layer, but the API for the
        # plugin currently takes a SQL object.  This can move to the service layer once a data
        # transfer object is defined instead.
        get_plugin_proxy().log_auditlog_entry(entry)

    def _id_for_group(self, group):
        # type: (str) -> int
        group_obj = Group.get(self.session, name=group)
        if not group_obj:
            raise GroupNotFoundException(group)
        return group_obj.id

    def _id_for_permission(self, permission):
        # type: (str) -> int
        permission_obj = Permission.get(self.session, name=permission)
        if not permission_obj:
            raise PermissionNotFoundException(permission)
        return permission_obj.id

    def _id_for_user(self, user):
        # type: (str) -> int
        user_obj = User.get(self.session, name=user)
        if not user_obj:
            raise UserNotFoundException(user)
        return user_obj.id

    def _to_audit_log_entry(self, entry):
        # type: (AuditLog) -> AuditLogEntry
        return AuditLogEntry(
            actor=entry.actor.username,
            action=entry.action,
            description=entry.description,
            on_user=entry.on_user.username if entry.on_user else None,
            on_group=entry.on_group.groupname if entry.on_group else None,
            on_permission=entry.on_permission.name if entry.on_permission else None,
        )
