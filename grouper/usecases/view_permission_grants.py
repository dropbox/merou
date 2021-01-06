from abc import ABCMeta, abstractmethod
from enum import Enum

from grouper.entities.pagination import PaginatedList, Pagination, PermissionGrantSortKey
from grouper.entities.permission_grant import (
    GroupPermissionGrant,
    ServiceAccountPermissionGrant,
)

from grouper.entities.audit_log_entry import AuditLogEntry
from grouper.entities.permission import Permission, PermissionAccess
from grouper.usecases.interfaces import AuditLogInterface, PermissionInterface, UserInterface
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Optional, Union

    GroupListType = PaginatedList[GroupPermissionGrant]
    ServiceAccountListType = PaginatedList[ServiceAccountPermissionGrant]
    GrantsListType = Union[GroupListType, ServiceAccountListType]


class ViewPermissionGrantsUI(metaclass=ABCMeta):
    """Abstract base class for UI for ListPermissions."""

    @abstractmethod
    def viewed_permission(
        self,
        permission,  # type: Permission
        grants,  # type: GrantsListType
        access,  # type: PermissionAccess
        audit_log_entries,  # type: List[AuditLogEntry]
    ):
        # type: (...) -> None
        pass

    @abstractmethod
    def view_permission_failed_not_found(self, name):
        # type: (str) -> None
        pass


GrantType = Enum("GrantType", "Group ServiceAccount")


class ViewPermissionGrants:
    """View a single permission."""

    def __init__(
        self,
        ui,  # type: ViewPermissionGrantsUI
        permission_service,  # type: PermissionInterface
        user_service,  # type: UserInterface
        audit_log_service,  # type: AuditLogInterface
    ):
        # type: (...) -> None
        self.ui = ui
        self.permission_service = permission_service
        self.user_service = user_service
        self.audit_log_service = audit_log_service

    def view_granted_permission(
        self,
        name,  # type: str
        actor,  # type: str
        audit_log_limit,  # type: int
        grant_type,  # type: GrantType
        pagination,  # type: Pagination[PermissionGrantSortKey]
        argument=None,  # type: Optional[str]
    ):
        # type: (...) -> None

        permission = self.permission_service.permission(name)
        if not permission:
            self.ui.view_permission_failed_not_found(name)
            return

        grants = (
            self.permission_service.service_account_paginated_grants_for_permission(
                name, pagination, argument
            )
            if grant_type == GrantType.ServiceAccount
            else self.permission_service.group_paginated_grants_for_permission(
                name, pagination, argument
            )
        )  # type: GrantsListType

        audit_log = self.audit_log_service.entries_affecting_permission(name, audit_log_limit)
        access = self.user_service.permission_access_for_user(actor, name)
        self.ui.viewed_permission(permission, grants, access, audit_log)
