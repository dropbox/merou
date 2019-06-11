from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from six import with_metaclass

from grouper.entities.pagination import Pagination

if TYPE_CHECKING:
    from grouper.entities.pagination import PaginatedList
    from grouper.entities.permission import Permission
    from grouper.usecases.interfaces import PermissionInterface, UserInterface


class ListPermissionsSortKey(Enum):
    NONE = "none"
    NAME = "name"
    DATE = "date"


class ListPermissionsUI(with_metaclass(ABCMeta, object)):
    """Abstract base class for UI for ListPermissions."""

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
        # type: (str, Pagination[ListPermissionsSortKey], bool) -> None
        permissions = self.permission_service.list_permissions(pagination, audited_only)
        can_create = self.user_service.user_can_create_permissions(user)
        self.ui.listed_permissions(permissions, can_create)

    def simple_list_permissions(self):
        # type: () -> None
        """List permissions with no selection, pagination, or current user."""
        pagination = Pagination(
            sort_key=ListPermissionsSortKey.NONE, reverse_sort=False, offset=0, limit=None
        )
        permissions = self.permission_service.list_permissions(pagination, False)
        self.ui.listed_permissions(permissions, False)
