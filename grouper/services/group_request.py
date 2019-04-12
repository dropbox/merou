from typing import TYPE_CHECKING

from grouper.entities.group_request import GroupRequestStatus
from grouper.usecases.interfaces import GroupRequestInterface

if TYPE_CHECKING:
    from grouper.repositories.group_request import GroupRequestRepository
    from grouper.usecases.authorization import Authorization
    from grouper.usecases.interfaces import AuditLogInterface


class GroupRequestService(GroupRequestInterface):
    """High-level logic to manipulate requests to join groups."""

    def __init__(self, group_request_repository, audit_log_service):
        # type: (GroupRequestRepository, AuditLogInterface) -> None
        self.group_request_repository = group_request_repository
        self.audit_log_service = audit_log_service

    def cancel_all_requests_for_user(self, user, reason, authorization):
        # type: (str, str, Authorization) -> None
        pending_requests = self.group_request_repository.pending_requests_for_user(user)
        for request in pending_requests:
            self.group_request_repository.cancel_user_request(request, reason, authorization)
            self.audit_log_service.log_user_group_request_status_change(
                request, GroupRequestStatus.CANCELLED, authorization
            )
