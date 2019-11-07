from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from grouper.entities.permission import PermissionNotFoundException
from grouper.usecases.authorization import Authorization

if TYPE_CHECKING:
    from grouper.entities.permission_grant import GroupPermissionGrant
    from grouper.usecases.interfaces import (
        GroupInterface,
        PermissionInterface,
        ServiceAccountInterface,
        TransactionInterface,
        UserInterface,
    )
    from typing import List


class GrantPermissionToServiceAccountUI(metaclass=ABCMeta):
    @abstractmethod
    def grant_permission_to_service_account_failed_invalid_argument(
        self, permission, argument, service, message
    ):
        # type: (str, str, str, str) -> None
        pass

    @abstractmethod
    def grant_permission_to_service_account_failed_permission_denied(
        self, permission, argument, service, message
    ):
        # type: (str, str, str, str) -> None
        pass

    @abstractmethod
    def grant_permission_to_service_account_failed_permission_not_found(self, permission, service):
        # type: (str, str) -> None
        pass

    @abstractmethod
    def grant_permission_to_service_account_failed_service_account_not_found(self, service):
        # type: (str) -> None
        pass

    @abstractmethod
    def granted_permission_to_service_account(self, permission, argument, service):
        # type; (str, str, str) -> None
        pass


class GrantPermissionToServiceAccount:
    def __init__(
        self,
        actor,  # type: str
        ui,  # type: GrantPermissionToServiceAccountUI
        permission_service,  # type: PermissionInterface
        service_account_service,  # type: ServiceAccountInterface
        user_service,  # type: UserInterface
        group_service,  # type: GroupInterface
        transaction_service,  # type: TransactionInterface
    ):
        # type: (...) -> None
        self.actor = actor
        self.ui = ui
        self.permission_service = permission_service
        self.service_account_service = service_account_service
        self.user_service = user_service
        self.group_service = group_service
        self.transaction_service = transaction_service

    def can_grant_permissions_for_service_account(self, service):
        # type: (str) -> bool
        if not self.service_account_service.service_account_is_enabled(service):
            return False

        # If the actor is a permission admin, they can grant any permission to the service account.
        # Otherwise, they have to be a member of the owning group.
        if self.service_account_service.service_account_exists(self.actor):
            return self.service_account_service.service_account_is_permission_admin(self.actor)
        elif self.user_service.user_is_permission_admin(self.actor):
            return True
        else:
            owner = self.service_account_service.owner_of_service_account(service)
            return owner in self.user_service.groups_of_user(self.actor)

    def grant_permission_to_service_account(self, permission, argument, service):
        # type: (str, str, str) -> None
        if not self.service_account_service.service_account_is_enabled(service):
            self.ui.grant_permission_to_service_account_failed_service_account_not_found(service)
            return

        valid, error = self.permission_service.is_valid_permission_argument(permission, argument)
        if not valid:
            assert error
            self.ui.grant_permission_to_service_account_failed_invalid_argument(
                permission, argument, service, error
            )
            return

        # If the actor is a permission admin, they can grant any permission to the service account.
        # Otherwise, they have to be a member of the owning group and the permission and argument
        # being granted must have been granted to the owning group.
        if self.service_account_service.service_account_exists(self.actor):
            allowed = self.service_account_service.service_account_is_permission_admin(self.actor)
        elif self.user_service.user_is_permission_admin(self.actor):
            allowed = True
        else:
            owner = self.service_account_service.owner_of_service_account(service)
            if owner in self.user_service.groups_of_user(self.actor):
                allowed = self.group_service.group_has_matching_permission_grant(
                    owner, permission, argument
                )
                if not allowed:
                    message = "The group {} does not have that permission".format(owner)
                    self.ui.grant_permission_to_service_account_failed_permission_denied(
                        permission, argument, service, message
                    )
                    return
            else:
                allowed = False
        if not allowed:
            self.ui.grant_permission_to_service_account_failed_permission_denied(
                permission, argument, service, "Permission denied"
            )
            return

        authorization = Authorization(self.actor)
        with self.transaction_service.transaction():
            try:
                self.service_account_service.grant_permission_to_service_account(
                    permission, argument, service, authorization
                )
            except PermissionNotFoundException:
                self.ui.grant_permission_to_service_account_failed_permission_not_found(
                    permission, service
                )
                return
        self.ui.granted_permission_to_service_account(permission, argument, service)

    def service_account_exists_with_owner(self, service, owner):
        # type: (str, str) -> bool
        """Returns True if the given service account exists, is enabled, and has that owner."""
        if not self.service_account_service.service_account_is_enabled(service):
            return False
        if not self.service_account_service.owner_of_service_account(service) == owner:
            return False
        return True

    def permission_grants_for_group(self, group):
        # type: (str) -> List[GroupPermissionGrant]
        """List of all permissions granted to a group.

        Used by the UI to populate the dropdown list of permissions that are eligible for
        delegation to the service account.
        """
        return self.group_service.permission_grants_for_group(group)
