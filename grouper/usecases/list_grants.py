from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grouper.entities.permission_grant import UniqueGrantsOfPermission
    from grouper.usecases.interfaces import PermissionInterface
    from typing import Dict


class ListGrantsUI(metaclass=ABCMeta):
    """Abstract base class for UI for ListGrants."""

    @abstractmethod
    def listed_grants(self, grants):
        # type: (Dict[str, UniqueGrantsOfPermission]) -> None
        pass

    @abstractmethod
    def listed_grants_of_permission(self, permission, grants):
        # type: (str, UniqueGrantsOfPermission) -> None
        pass


class ListGrants:
    """List all permission grants by permission, expanding the graph."""

    def __init__(self, ui, permission_service):
        # type: (ListGrantsUI, PermissionInterface) -> None
        self.ui = ui
        self.permission_service = permission_service

    def list_grants(self):
        # type: () -> None
        grants = self.permission_service.all_grants()
        self.ui.listed_grants(grants)

    def list_grants_of_permission(self, permission):
        # type: (str) -> None
        grants = self.permission_service.all_grants_of_permission(permission)
        self.ui.listed_grants_of_permission(permission, grants)
