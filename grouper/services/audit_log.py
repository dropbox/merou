from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grouper.entities.group_request import GroupRequestStatus, UserGroupRequest
    from grouper.repositories.audit_log import AuditLogRepository
    from grouper.usecases.authorization import Authorization


class AuditLogService(object):
    """Updates the audit log when changes are made."""

    def __init__(self, audit_log_repository):
        # type: (AuditLogRepository) -> None
        self.audit_log_repository = audit_log_repository

    def log_create_service_account_from_disabled_user(self, user, authorization):
        # type: (str, Authorization) -> None
        self.audit_log_repository.log(
            authorization=authorization,
            action="create_service_account_from_disabled_user",
            description="Convert a disabled user into a disabled service account",
            on_user=user,
        )

    def log_disable_permission(self, permission, authorization):
        # type: (str, Authorization) -> None
        self.audit_log_repository.log(
            authorization=authorization,
            action="disable_permission",
            description="Disabled permission",
            on_permission=permission,
        )

    def log_disable_user(self, username, authorization):
        # type: (str, Authorization) -> None
        self.audit_log_repository.log(
            authorization=authorization,
            action="disable_user",
            description="Disabled user",
            on_user=username,
        )

    def log_enable_service_account(self, user, owner, authorization):
        # type: (str, str, Authorization) -> None
        self.audit_log_repository.log(
            authorization=authorization,
            action="enable_service_account",
            description="Enabled service account",
            on_user=user,
            on_group=owner,
        )

    def log_user_group_request_status_change(self, request, status, authorization):
        # type: (UserGroupRequest, GroupRequestStatus, Authorization) -> None
        self.audit_log_repository.log(
            authorization=authorization,
            action="update_request",
            description="Updated request to status: {}".format(status.value),
            on_group=request.group,
            on_user=request.requester,
        )
