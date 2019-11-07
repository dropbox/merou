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

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.plugin.proxy import PluginProxy
    from grouper.usecases.authorization import Authorization
    from typing import List, Optional


class AuditLogRepository:
    """SQL storage layer for audit log entries."""

    def __init__(self, session, plugins):
        # type: (Session, PluginProxy) -> None
        self.session = session
        self.plugins = plugins

    def entries_affecting_group(self, group, limit):
        # type: (str, int) -> List[AuditLogEntry]
        group_obj = Group.get(self.session, name=group)
        if not group_obj:
            return []
        results = (
            self.session.query(AuditLog)
            .filter(AuditLog.on_group_id == group_obj.id)
            .order_by(desc(AuditLog.log_time))
            .limit(limit)
        )
        return [self._to_audit_log_entry(e) for e in results]

    def entries_affecting_permission(self, permission, limit):
        # type: (str, int) -> List[AuditLogEntry]
        permission_obj = Permission.get(self.session, name=permission)
        if not permission_obj:
            return []
        results = (
            self.session.query(AuditLog)
            .filter(AuditLog.on_permission_id == permission_obj.id)
            .order_by(desc(AuditLog.log_time))
            .limit(limit)
        )
        return [self._to_audit_log_entry(e) for e in results]

    def entries_affecting_user(self, user, limit):
        # type: (str, int) -> List[AuditLogEntry]
        user_obj = User.get(self.session, name=user)
        if not user_obj:
            return []
        results = (
            self.session.query(AuditLog)
            .filter(AuditLog.on_user_id == user_obj.id)
            .order_by(desc(AuditLog.log_time))
            .limit(limit)
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
        date=None,  # type: Optional[datetime]
    ):
        # type: (...) -> None
        """Log an action to the audit log.

        Arguments don't cover all use cases yet.  This method will be expanded as further use cases
        are ported to this service.
        """
        actor = self._id_for_user(authorization.actor)
        if not date:
            date = datetime.utcnow()

        # We currently have no way to log audit log entries for objects that no longer exist.  This
        # should eventually be fixed via a schema change to use strings for all fields of the audit
        # log.  For now, we'll die with an exception.
        user = self._id_for_user(on_user) if on_user else None
        group = self._id_for_group(on_group) if on_group else None
        permission = self._id_for_permission(on_permission) if on_permission else None

        entry = AuditLog(
            actor_id=actor,
            log_time=date,
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
        self.plugins.log_auditlog_entry(entry)

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
            date=entry.log_time,
            actor=entry.actor.username,
            action=entry.action,
            description=entry.description,
            on_user=entry.on_user.username if entry.on_user else None,
            on_group=entry.on_group.groupname if entry.on_group else None,
            on_permission=entry.on_permission.name if entry.on_permission else None,
        )
