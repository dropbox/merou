from typing import TYPE_CHECKING

from grouper.entities.user import (
    UserHasPendingRequestsException,
    UserIsEnabledException,
    UserIsMemberOfGroupsException,
)
from grouper.usecases.interfaces import ServiceAccountInterface

if TYPE_CHECKING:
    from grouper.repositories.group_edge import GroupEdgeRepository
    from grouper.repositories.group_request import GroupRequestRepository
    from grouper.repositories.service_account import ServiceAccountRepository
    from grouper.repositories.user import UserRepository
    from grouper.usecases.authorization import Authorization
    from grouper.usecases.interfaces import AuditLogInterface


class ServiceAccountService(ServiceAccountInterface):
    """High-level logic to manipulate service accounts."""

    def __init__(
        self,
        user_repository,  # type: UserRepository
        service_account_repository,  # type: ServiceAccountRepository
        group_edge_repository,  # type: GroupEdgeRepository
        group_request_repository,  # type: GroupRequestRepository
        audit_log_service,  # type: AuditLogInterface
    ):
        # type: (...) -> None
        self.user_repository = user_repository
        self.service_account_repository = service_account_repository
        self.group_edge_repository = group_edge_repository
        self.group_request_repository = group_request_repository
        self.audit_log = audit_log_service

    def create_service_account_from_disabled_user(self, user, authorization):
        # type: (str, Authorization) -> None
        if self.user_repository.user_is_enabled(user):
            raise UserIsEnabledException(user)
        if self.group_edge_repository.groups_of_user(user) != []:
            raise UserIsMemberOfGroupsException(user)
        if self.group_request_repository.pending_requests_for_user(user) != []:
            raise UserHasPendingRequestsException(user)

        # WARNING: This logic relies on the fact that the user and service account repos
        # are in fact the same thing, as it never explicitly removes the user from the
        # user repo. This is a temporary breaking of the abstractions and will have to be
        # cleaned up once the repositories are properly separate.
        self.service_account_repository.mark_disabled_user_as_service_account(user)

        self.audit_log.log_create_service_account_from_disabled_user(user, authorization)

    def enable_service_account(self, user, owner, authorization):
        # type: (str, str, Authorization) -> None
        self.service_account_repository.assign_service_account_to_group(user, owner)
        self.service_account_repository.enable_service_account(user)

        self.audit_log.log_enable_service_account(user, owner, authorization)
