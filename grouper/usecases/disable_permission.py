from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from grouper.usecases.authorization import Authorization
from grouper.usecases.interfaces import PermissionNotFoundException

if TYPE_CHECKING:
    from grouper.models.base.session import Session  # noqa: F401
    from grouper.usecases.interfaces import PermissionInterface  # noqa: F401


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

    def __init__(self, session, actor, ui, service):
        # type: (Session, str, DisablePermissionUI, PermissionInterface) -> None
        self.session = session
        self.actor = actor
        self.ui = ui
        self.service = service

    def disable_permission(self, name):
        # type: (str) -> None
        if self.service.is_system_permission(name):
            self.ui.disable_permission_failed_because_system_permission(name)
        elif not self.service.user_is_permission_admin(self.actor):
            self.ui.disable_permission_failed_because_permission_denied(name)
        else:
            authorization = Authorization(self.actor)
            try:
                self.service.disable_permission(name, authorization)
            except PermissionNotFoundException:
                self.ui.disable_permission_failed_because_not_found(name)
            else:
                self.ui.disabled_permission(name)
