from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from grouper.models.audit_log import AuditLog, AuditLogCategory
from grouper.models.permission import Permission
from grouper.models.user import User
from grouper.plugin import get_plugin_proxy

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.usecases.authorization import Authorization


class UnknownUserException(Exception):
    """User involved in a logged action does not exist."""

    pass


class AuditLogAction(Enum):
    """Possible actions and descriptions for the audit log.

    The logged action will be the lowercase form of the enum name, and the enum value will be used
    as the description.
    """

    DISABLE_PERMISSION = "Disabled permission"


class AuditLogService(object):
    """Updates the audit log when changes are made."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def log_disable_permission(self, permission, authorization):
        # type: (str, Authorization) -> None
        permission_obj = Permission.get(self.session, name=permission)
        self._log(authorization, AuditLogAction.DISABLE_PERMISSION, on_permission=permission_obj)

    def _log(
        self,
        authorization,  # type: Authorization
        action,  # type: AuditLogAction
        on_permission,  # type: Permission
        category=AuditLogCategory.general,  # type: AuditLogCategory
    ):
        # type: (...) -> None
        """Internal method to log an action to the audit log.

        All uses of AuditLog.log should be replaced with more specific entry points like the above,
        which in turn dispatch to this private method to make the database change.  Arguments don't
        cover all use cases yet.  This method will be expanded as further use cases are ported to
        this service.
        """
        actor = User.get(self.session, name=authorization.actor)
        if not actor:
            raise UnknownUserException("unknown actor {}".format(authorization.actor))
        entry = AuditLog(
            actor_id=actor.id,
            log_time=datetime.utcnow(),
            action=action.name.lower(),
            description=action.value,
            on_user_id=None,
            on_group_id=None,
            on_permission_id=on_permission.id,
            on_tag_id=None,
            category=int(category),
        )
        entry.add(self.session)
        get_plugin_proxy().log_auditlog_entry(entry)
