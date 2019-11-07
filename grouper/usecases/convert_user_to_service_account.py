from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from grouper.usecases.authorization import Authorization

if TYPE_CHECKING:
    from grouper.usecases.interfaces import (
        GroupRequestInterface,
        ServiceAccountInterface,
        TransactionInterface,
        UserInterface,
    )


class ConvertUserToServiceAccountUI(metaclass=ABCMeta):
    """Abstract base class for UI for ConvertUserToServiceAccount."""

    @abstractmethod
    def convert_user_to_service_account_failed_permission_denied(self, user):
        # type: (str) -> None
        pass

    @abstractmethod
    def convert_user_to_service_account_failed_user_is_in_groups(self, user):
        # type: (str) -> None
        pass

    @abstractmethod
    def converted_user_to_service_account(self, user, owner):
        # type: (str, str) -> None
        pass


class ConvertUserToServiceAccount:
    """Delete a user and create a service account with the same name.

    The use case doesn't exactly do that now due to limitations of the data model, but semantically
    that should be the effect.
    """

    def __init__(
        self,
        actor,  # type: str
        ui,  # type: ConvertUserToServiceAccountUI
        user_service,  # type: UserInterface
        service_account_service,  # type: ServiceAccountInterface
        group_request_service,  # type: GroupRequestInterface
        transaction_service,  # type: TransactionInterface
    ):
        self.actor = actor
        self.ui = ui
        self.user_service = user_service
        self.service_account_service = service_account_service
        self.group_request_service = group_request_service
        self.transaction_service = transaction_service

    def convert_user_to_service_account(self, user, owner):
        # type: (str, str) -> None
        if not self.user_service.user_is_user_admin(self.actor):
            self.ui.convert_user_to_service_account_failed_permission_denied(user)
        elif self.user_service.groups_of_user(user) != []:
            self.ui.convert_user_to_service_account_failed_user_is_in_groups(user)
        else:
            authorization = Authorization(self.actor)
            with self.transaction_service.transaction():
                self.group_request_service.cancel_all_requests_for_user(
                    user, "User converted to service account", authorization
                )
                self.user_service.disable_user(user, authorization)
                self.service_account_service.create_service_account_from_disabled_user(
                    user, authorization
                )
                self.service_account_service.enable_service_account(user, owner, authorization)
            self.ui.converted_user_to_service_account(user, owner)
