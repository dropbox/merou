from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from grouper.entities.pagination import Pagination

if TYPE_CHECKING:
    from grouper.entities.pagination import PaginatedList
    from grouper.entities.permission import Permission
    from grouper.usecases.interfaces import PermissionInterface, UserInterface


class ListPermissionsSortKey(Enum):
    NAME = "name"
    DATE = "date"


ListPermissionsPagination = Pagination[ListPermissionsSortKey]


class ListPermissionsUI(object):
    """Abstract base class for UI for ListPermissions."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def listed_permissions(self, permissions, can_create):
        # type: (PaginatedList[Permission], bool) -> None
        pass


class ListPermissions(object):
    """List all permissions."""

    def __init__(self, ui, permission_service, user_service):
        # type: (ListPermissionsUI, PermissionInterface, UserInterface) -> None
        self.ui = ui
        self.permission_service = permission_service
        self.user_service = user_service

    def list_permissions(self, user, pagination, audited_only):
        # type: (str, ListPermissionsPagination, bool) -> None
        permissions = self.permission_service.list_permissions(pagination, audited_only)
        can_create = self.user_service.user_can_create_permissions(user)
        self.ui.listed_permissions(permissions, can_create)
