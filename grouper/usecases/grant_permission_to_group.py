from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from grouper.entities.permission import PermissionNotFoundException
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


class GrantPermissionToGroupUI(metaclass=ABCMeta):
    @abstractmethod
    def grant_permission_to_group_failed_invalid_argument(
        self, permission, argument, group, message
    ):
        # type: (str, str, str, str) -> None
        pass

    @abstractmethod
    def grant_permission_to_group_failed_permission_denied(
        self, permission, argument, group, message
    ):
        # type: (str, str, str, str) -> None
        pass

    @abstractmethod
    def grant_permission_to_group_failed_permission_not_found(self, permission, group):
        # type: (str, str) -> None
        pass

    @abstractmethod
    def grant_permission_to_group_failed_group_not_found(self, group):
        # type: (str) -> None
        pass

    @abstractmethod
    def grant_permission_to_group_failed_permission_already_exists(self, group):
        # type: (str) -> None
        pass

    @abstractmethod
    def granted_permission_to_group(self, permission, argument, group):
        # type; (str, str, str) -> None
        pass


class GrantPermissionToGroup:
    def __init__(
        self,
        actor,  # type: str
        ui,  # type: GrantPermissionToGroupUI
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

    def permissions_grantable(self):
        # The actor can grant a permission to the group if the actor independently has the
        # ability to grant the permission, as a permission admin or because of grants of
        # grouper.permission.grants.

        actor_grantable_perms = []  # type: List[Tuple[str, str]]
        if self.service_account_service.service_account_exists(self.actor):
            p = self.service_account_service.permissions_grantable_by_service_account(self.actor)
            actor_grantable_perms = p  # line length :( if you see a nicer way, do it
        else:  # actor is not a service account, and is thus a normal user
            actor_grantable_perms = self.user_service.permissions_grantable_by_user(self.actor)

        return sorted(actor_grantable_perms, key=lambda x: x[0] + x[1])

    def grant_permission_to_group(self, permission, argument, group):
        # type: (str, str, str) -> None
        if not self.group_service.group_exists(group):
            self.ui.grant_permission_to_group_failed_group_not_found(group)
            return

        if self.group_service.group_has_matching_permission_grant(group, permission, argument):
            self.ui.grant_permission_to_group_failed_permission_already_exists(group)
            return

        valid, error = self.permission_service.is_valid_permission_argument(permission, argument)
        if not valid:
            assert error
            self.ui.grant_permission_to_group_failed_invalid_argument(
                permission, argument, group, error
            )
            return

        allowed = False
        grantable = self.permissions_grantable()
        for grantable_perm, grantable_arg in grantable:
            if grantable_perm == permission and matches_glob(grantable_arg, argument):
                allowed = True
                break
        if not allowed:
            message = (
                "Permission denied. Actor {actor} does not have the ability to"
                "grant the permission {permission} with argument {argument}."
            ).format(actor=self.actor, permission=permission, argument=argument)
            if argument == "":
                message += " (Did you mean to leave the argument empty?)"
            self.ui.grant_permission_to_group_failed_permission_denied(
                permission, argument, group, message
            )
            return

        with self.transaction_service.transaction():
            try:
                self.group_service.grant_permission_to_group(permission, argument, group)
            except PermissionNotFoundException:
                # It should be impossible to hit this exception. In order to get this far, the
                # perm must be on the list of perms the actor can grant, and thus must exist.
                # Leaving the logic here however in case that changes in the future.
                self.ui.grant_permission_to_group_failed_permission_not_found(permission, group)
                return
        self.ui.granted_permission_to_group(permission, argument, group)
