import re
from typing import TYPE_CHECKING

from grouper.constants import MAX_NAME_LENGTH, SERVICE_ACCOUNT_VALIDATION, USER_ADMIN
from grouper.entities.user import (
    UserHasPendingRequestsException,
    UserIsEnabledException,
    UserIsMemberOfGroupsException,
)
from grouper.usecases.interfaces import ServiceAccountInterface

if TYPE_CHECKING:
    from grouper.entities.permission_grant import ServiceAccountPermissionGrant
    from grouper.repositories.group_edge import GroupEdgeRepository
    from grouper.repositories.group_request import GroupRequestRepository
    from grouper.repositories.interfaces import PermissionGrantRepository
    from grouper.repositories.service_account import ServiceAccountRepository
    from grouper.repositories.user import UserRepository
    from grouper.settings import Settings
    from grouper.usecases.authorization import Authorization
    from grouper.usecases.interfaces import AuditLogInterface
    from typing import List, Optional, Tuple


class ServiceAccountService(ServiceAccountInterface):
    """High-level logic to manipulate service accounts."""

    def __init__(
        self,
        settings,  # type: Settings
        user_repository,  # type: UserRepository
        service_account_repository,  # type: ServiceAccountRepository
        permission_grant_repository,  # type: PermissionGrantRepository
        group_edge_repository,  # type: GroupEdgeRepository
        group_request_repository,  # type: GroupRequestRepository
        audit_log_service,  # type: AuditLogInterface
    ):
        # type: (...) -> None
        self.settings = settings
        self.user_repository = user_repository
        self.service_account_repository = service_account_repository
        self.permission_grant_repository = permission_grant_repository
        self.group_edge_repository = group_edge_repository
        self.group_request_repository = group_request_repository
        self.audit_log = audit_log_service

    def create_service_account(self, service, owner, machine_set, description, authorization):
        # type: (str, str, str, str, Authorization) -> None
        self.service_account_repository.create_service_account(
            service, owner, machine_set, description
        )
        self.audit_log.log_create_service_account(service, owner, authorization)

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

    def is_valid_service_account_name(self, name):
        # type: (str) -> Tuple[bool, Optional[str]]
        """Check if the given name is valid for use as a service account.

        Returns:
            Tuple whose first element is True or False indicating whether it is valid, and whose
            second element is None if valid and an error message if not.
        """
        if len(name) > MAX_NAME_LENGTH:
            error = "{} is longer than {} characters".format(name, MAX_NAME_LENGTH)
            return (False, error)

        if not re.match("^{}$".format(SERVICE_ACCOUNT_VALIDATION), name):
            error = "{} is not a valid service account name (does not match {})".format(
                name, SERVICE_ACCOUNT_VALIDATION
            )
            return (False, error)

        if name.split("@")[-1] != self.settings.service_account_email_domain:
            error = "All service accounts must end in @{}".format(
                self.settings.service_account_email_domain
            )
            return (False, error)

        return (True, None)

    def permission_grants_for_service_account(self, service):
        # type: (str) -> List[ServiceAccountPermissionGrant]
        return self.permission_grant_repository.permission_grants_for_service_account(service)

    def service_account_exists(self, service):
        # type: (str) -> bool
        return self.service_account_repository.service_account_exists(service)

    def service_account_is_user_admin(self, service):
        # type: (str) -> bool
        return self.permission_grant_repository.service_account_has_permission(service, USER_ADMIN)
