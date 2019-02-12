from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from grouper.entities.permission import PermissionNotFoundException
from grouper.usecases.authorization import Authorization

if TYPE_CHECKING:
    from grouper.usecases.interfaces import (
        PermissionInterface,
        TransactionInterface,
        UserInterface,
    )


class DisablePermissionUI(object):
    """Abstract base class for UI for DisablePermission."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def disabled_permission(self, name):
        # type: (str) -> None
        pass

    @abstractmethod
    def disable_permission_failed_because_not_found(self, name):
        # type: (str) -> None
        pass

    @abstractmethod
    def disable_permission_failed_because_permission_denied(self, name):
        # type: (str) -> None
        pass

    @abstractmethod
    def disable_permission_failed_because_system_permission(self, name):
        # type: (str) -> None
        pass


class DisablePermission(object):
    """Disable a permission."""

    def __init__(
        self,
        actor,  # type: str
        ui,  # type: DisablePermissionUI
        permission_service,  # type: PermissionInterface
        user_service,  # type: UserInterface
        transaction_service,  # type: TransactionInterface
    ):
        # type: (...) -> None
        self.actor = actor
        self.ui = ui
        self.permission_service = permission_service
        self.user_service = user_service
        self.transaction_service = transaction_service

    def disable_permission(self, name):
        # type: (str) -> None
        if self.permission_service.is_system_permission(name):
            self.ui.disable_permission_failed_because_system_permission(name)
        elif not self.user_service.user_is_permission_admin(self.actor):
            self.ui.disable_permission_failed_because_permission_denied(name)
        else:
            authorization = Authorization(self.actor)
            try:
                self.transaction_service.start_transaction()
                self.permission_service.disable_permission(name, authorization)
                self.transaction_service.commit()
            except PermissionNotFoundException:
                self.ui.disable_permission_failed_because_not_found(name)
            else:
                self.ui.disabled_permission(name)
