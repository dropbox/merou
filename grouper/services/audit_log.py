from typing import TYPE_CHECKING

from grouper.usecases.interfaces import AuditLogInterface

if TYPE_CHECKING:
    from datetime import datetime
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.entities.group_request import GroupRequestStatus, UserGroupRequest
    from grouper.repositories.audit_log import AuditLogRepository
    from grouper.usecases.authorization import Authorization
    from typing import List, Optional


class AuditLogService(AuditLogInterface):
    """Updates the audit log when changes are made.

    The date parameter to the log methods is primarily for use in tests, where to get a consistent
    sort order the audit log entries may need to be spaced out over time.  If not set, the default
    is the current time.
    """

    def __init__(self, audit_log_repository):
        # type: (AuditLogRepository) -> None
        self.audit_log_repository = audit_log_repository

    def log_create_service_account_from_disabled_user(self, user, authorization, date=None):
        # type: (str, Authorization, Optional[datetime]) -> None
        self.audit_log_repository.log(
            authorization=authorization,
            action="create_service_account_from_disabled_user",
            description="Convert a disabled user into a disabled service account",
            on_user=user,
            date=date,
        )

    def log_create_permission(self, permission, authorization, date=None):
        # type: (str, Authorization, Optional[datetime]) -> None
        self.audit_log_repository.log(
            authorization=authorization,
            action="create_permission",
            description="Created permission.",
            on_permission=permission,
            date=date,
        )

    def log_disable_permission(self, permission, authorization, date=None):
        # type: (str, Authorization, Optional[datetime]) -> None
        self.audit_log_repository.log(
            authorization=authorization,
            action="disable_permission",
            description="Disabled permission",
            on_permission=permission,
            date=date,
        )

    def log_disable_user(self, username, authorization, date=None):
        # type: (str, Authorization, Optional[datetime]) -> None
        self.audit_log_repository.log(
            authorization=authorization,
            action="disable_user",
            description="Disabled user",
            on_user=username,
            date=date,
        )

    def log_enable_service_account(self, user, owner, authorization, date=None):
        # type: (str, str, Authorization, Optional[datetime]) -> None
        self.audit_log_repository.log(
            authorization=authorization,
            action="enable_service_account",
            description="Enabled service account",
            on_user=user,
            on_group=owner,
            date=date,
        )

    def log_user_group_request_status_change(self, request, status, authorization, date=None):
        # type: (UserGroupRequest, GroupRequestStatus, Authorization, Optional[datetime]) -> None
        self.audit_log_repository.log(
            authorization=authorization,
            action="update_request",
            description="Updated request to status: {}".format(status.value),
            on_group=request.group,
            on_user=request.requester,
            date=date,
        )

    def entries_affecting_permission(self, permission, limit):
        # type: (str, int) -> List[AuditLogEntry]
        return self.audit_log_repository.entries_affecting_permission(permission, limit)
