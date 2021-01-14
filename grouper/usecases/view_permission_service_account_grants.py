from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Optional

from grouper.entities.pagination import PaginatedList, Pagination, PermissionGrantSortKey
from grouper.entities.permission import Permission
from grouper.entities.permission_grant import ServiceAccountPermissionGrant
from grouper.usecases.interfaces import PermissionInterface, UserInterface

ServiceAccountListType = PaginatedList[ServiceAccountPermissionGrant]


class ViewPermissionServiceAccountGrantsUI(metaclass=ABCMeta):
    """Abstract base class for UI for ListPermissions."""

    @abstractmethod
    def viewed_permission(
        self,
        permission,  # type: Permission
        grants,  # type: ServiceAccountListType
    ):
        # type: (...) -> None
        pass

    @abstractmethod
    def view_permission_failed_not_found(self, name):
        # type: (str) -> None
        pass


GrantType = Enum("GrantType", "Group ServiceAccount")


class ViewPermissionServiceAccountGrants:
    """View a single permission."""

    def __init__(
        self,
        ui,  # type: ViewPermissionServiceAccountGrantsUI
        permission_service,  # type: PermissionInterface
        user_service,  # type: UserInterface
    ):
        # type: (...) -> None
        self.ui = ui
        self.permission_service = permission_service
        self.user_service = user_service

    def view_granted_permission(
        self,
        name,  # type: str
        actor,  # type: str
        pagination,  # type: Pagination[PermissionGrantSortKey]
        argument=None,  # type: Optional[str]
    ):
        # type: (...) -> None

        permission = self.permission_service.permission(name)
        if not permission:
            self.ui.view_permission_failed_not_found(name)
            return

        grants = self.permission_service.service_account_paginated_grants_for_permission(
            name, pagination, argument
        )

        self.ui.viewed_permission(permission, grants)
