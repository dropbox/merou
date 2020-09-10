from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from grouper.entities.group import GroupNotFoundException
from grouper.plugin.exceptions import PluginRejectedMachineSet
from grouper.usecases.authorization import Authorization

if TYPE_CHECKING:
    from grouper.plugin.proxy import PluginProxy
    from grouper.settings import Settings
    from grouper.usecases.interfaces import (
        ServiceAccountInterface,
        TransactionInterface,
        UserInterface,
    )
    from typing import Dict, Optional


class CreateServiceAccountUI(metaclass=ABCMeta):
    """Abstract base class for UI for CreateServiceAccount."""

    @abstractmethod
    def create_service_account_failed_already_exists(self, service, owner):
        # type: (str, str) -> None
        pass

    @abstractmethod
    def create_service_account_failed_invalid_name(self, service, owner, message):
        # type: (str, str, str) -> None
        pass

    @abstractmethod
    def create_service_account_failed_invalid_machine_set(
        self, service, owner, machine_set, message
    ):
        # type: (str, str, str, str) -> None
        pass

    @abstractmethod
    def create_service_account_failed_invalid_owner(self, service, owner):
        # type: (str, str) -> None
        pass

    @abstractmethod
    def create_service_account_failed_permission_denied(self, service, owner):
        # type: (str, str) -> None
        pass

    @abstractmethod
    def created_service_account(self, service, owner):
        # type: (str, str) -> None
        pass


class CreateServiceAccount:
    """Create a new service account."""

    def __init__(
        self,
        actor,  # type: str
        ui,  # type: CreateServiceAccountUI
        settings,  # type: Settings
        plugins,  # type: PluginProxy
        service_account_service,  # type: ServiceAccountInterface
        user_service,  # type: UserInterface
        transaction_service,  # type: TransactionInterface
    ):
        # type: (...) -> None
        self.actor = actor
        self.ui = ui
        self.settings = settings
        self.plugins = plugins
        self.service_account_service = service_account_service
        self.user_service = user_service
        self.transaction_service = transaction_service

    def can_create_service_account(self, owner):
        # type: (str) -> bool
        """Whether the actor can create a service account owned by the given group.

        Creation is permitted if the actor is a user admin or if the actor is a user (not a service
        account) and is a member of the owning group.
        """
        if self.service_account_service.service_account_exists(self.actor):
            return self.service_account_service.service_account_is_user_admin(self.actor)
        elif owner in self.user_service.groups_of_user(self.actor):
            return True
        else:
            return self.user_service.user_is_user_admin(self.actor)

    def create_service_account(
        self, service, owner, machine_set, description, initial_metadata=None
    ):
        # type: (str, str, str, str, Optional[Dict[str,str]]) -> None
        if "@" not in service:
            service += "@" + self.settings.service_account_email_domain

        valid, error = self.service_account_service.is_valid_service_account_name(service)
        if not valid:
            assert error
            self.ui.create_service_account_failed_invalid_name(service, owner, error)
            return

        if not self.can_create_service_account(owner):
            self.ui.create_service_account_failed_permission_denied(service, owner)
            return

        if self.user_service.user_exists(service):
            self.ui.create_service_account_failed_already_exists(service, owner)
            return
        if self.service_account_service.service_account_exists(service):
            self.ui.create_service_account_failed_already_exists(service, owner)
            return

        if machine_set:
            try:
                self.plugins.check_machine_set(service, machine_set)
            except PluginRejectedMachineSet as e:
                self.ui.create_service_account_failed_invalid_machine_set(
                    service, owner, machine_set, str(e)
                )
                return

        authorization = Authorization(self.actor)
        with self.transaction_service.transaction():
            try:
                self.service_account_service.create_service_account(
                    service, owner, machine_set, description, initial_metadata, authorization
                )
            except GroupNotFoundException:
                self.ui.create_service_account_failed_invalid_owner(service, owner)
                return
        self.ui.created_service_account(service, owner)
