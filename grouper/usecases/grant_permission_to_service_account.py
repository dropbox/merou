from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from grouper.entities.permission import PermissionNotFoundException
from grouper.usecases.authorization import Authorization
from grouper.util import matches_glob

if TYPE_CHECKING:
    from grouper.usecases.interfaces import (
        GroupInterface,
        PermissionInterface,
        ServiceAccountInterface,
        TransactionInterface,
        UserInterface,
    )
    from typing import List, Tuple


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

    def permissions_grantable_to_service_account(self, service):
        # type: (str) -> List[Tuple[str, str]]
        """Returns all (permission, argument glob) pairs the actor can grant to the service."""
        if not self.service_account_service.service_account_is_enabled(service):
            return []

        # The actor can grant a permission to the service account for one of two reasons:
        # (1) The actor independently has the ability to grant the permission, as a permission
        #   admin or because of grants of grouper.permission.grants.
        # (2) The actor is a member of the owning group, and thus can grant any permissions
        #   that are granted to the owning group.
        actor_grantable_perms = []  # type: List[Tuple[str, str]]
        if self.service_account_service.service_account_exists(self.actor):
            p = self.service_account_service.permissions_grantable_by_service_account(self.actor)
            actor_grantable_perms = p  # line length :( if you see a nicer way, do it
        else:  # actor is not a service account, and is thus a normal user
            actor_grantable_perms = self.user_service.permissions_grantable_by_user(self.actor)

        owner_grantable_perms = []  # type: List[Tuple[str, str]]
        owner = self.service_account_service.owner_of_service_account(service)
        if owner in self.user_service.groups_of_user(self.actor):
            owner_grants = self.group_service.permission_grants_for_group(owner)
            owner_grantable_perms = [(g.permission, g.argument) for g in owner_grants]

        result = actor_grantable_perms + owner_grantable_perms
        return sorted(result, key=lambda x: x[0] + x[1])

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

        allowed = False
        grantable = self.permissions_grantable_to_service_account(service)
        for grantable_perm, grantable_arg in grantable:
            if grantable_perm == permission and matches_glob(grantable_arg, argument):
                allowed = True
                break
        if not allowed:
            message = (
                "Permission denied. To grant a permission to a service account you must either "
                "independently have the ability to grant that permission, or the owner group "
                "must have that permission and you must be a member of that owning group."
            )
            if argument == "":
                message += " (Did you mean to leave the argument field empty?)"
            self.ui.grant_permission_to_service_account_failed_permission_denied(
                permission, argument, service, message
            )
            return

        authorization = Authorization(self.actor)
        with self.transaction_service.transaction():
            try:
                self.service_account_service.grant_permission_to_service_account(
                    permission, argument, service, authorization
                )
            except PermissionNotFoundException:
                # It should be impossible to hit this exception. In order to get this far, the
                # perm must be on the list of perms the actor can grant, and thus must exist.
                # Leaving the logic here however in case that changes in the future.
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
