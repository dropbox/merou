from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from grouper.entities.pagination import (
        ListPermissionsSortKey,
        PaginatedList,
        Pagination,
        PermissionServiceAccountGrantSortKey,
        PermissionGroupGrantSortKey,
    )
    from grouper.entities.permission import Permission
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
        UniqueGrantsOfPermission,
    )
    from grouper.entities.user import User
    from grouper.repositories.audit_log import AuditLogRepository
    from grouper.repositories.checkpoint import CheckpointRepository
    from grouper.repositories.group import GroupRepository
    from grouper.repositories.group_request import GroupRequestRepository
    from grouper.repositories.schema import SchemaRepository
    from grouper.repositories.service_account import ServiceAccountRepository
    from grouper.repositories.transaction import TransactionRepository
    from typing import Dict, List, Optional


class GroupEdgeRepository(metaclass=ABCMeta):
    """Abstract base class for group edge repositories."""

    @abstractmethod
    def groups_of_user(self, username):
        # type: (str) -> List[str]
        pass


class PermissionRepository(metaclass=ABCMeta):
    """Abstract base class for permission repositories."""

    @abstractmethod
    def create_permission(
        self, name, description="", audited=False, enabled=True, created_on=None
    ):
        # type: (str, str, bool, bool, Optional[datetime]) -> None
        pass

    @abstractmethod
    def disable_permission(self, name):
        # type: (str) -> None
        pass

    @abstractmethod
    def get_permission(self, name):
        # type: (str) -> Optional[Permission]
        pass

    @abstractmethod
    def list_permissions(self, pagination, audited_only):
        # type: (Pagination[ListPermissionsSortKey], bool) -> PaginatedList[Permission]
        pass


class PermissionGrantRepository(metaclass=ABCMeta):
    """Abstract base class for permission grant repositories."""

    @abstractmethod
    def all_grants(self):
        # type: () -> Dict[str, UniqueGrantsOfPermission]
        pass

    @abstractmethod
    def all_grants_of_permission(self, permission):
        # type: (str) -> UniqueGrantsOfPermission
        pass

    @abstractmethod
    def grant_permission_to_group(self, permission, argument, group):
        # type: (str, str, str) -> None
        pass

    @abstractmethod
    def grant_permission_to_service_account(self, permission, argument, service):
        # type: (str, str, str) -> None
        pass

    @abstractmethod
    def group_paginated_grants_for_permission(
        self,
        name,  # type: str
        pagination,  # type: Pagination[PermissionGroupGrantSortKey]
        include_disabled_groups=False,  # type: bool
        argument=None,  # type: Optional[str]
    ):
        # type: (...) -> PaginatedList[GroupPermissionGrant]
        pass

    @abstractmethod
    def group_grants_for_permission(
        self,
        name,  # type: str
        include_disabled_groups=False,  # type: bool
        argument=None,  # type: Optional[str]
    ):
        # type: (...) -> List[GroupPermissionGrant]
        pass

    @abstractmethod
    def permission_grants_for_group(self, name):
        # type: (str) -> List[GroupPermissionGrant]
        pass

    @abstractmethod
    def permission_grants_for_service_account(self, name):
        # type: (str) -> List[ServiceAccountPermissionGrant]
        pass

    @abstractmethod
    def permission_grants_for_user(self, user):
        # type: (str) -> List[GroupPermissionGrant]
        pass

    @abstractmethod
    def revoke_all_group_grants(self, permission):
        # type: (str) -> List[GroupPermissionGrant]
        pass

    @abstractmethod
    def revoke_all_service_account_grants(self, permission):
        # type: (str) -> List[ServiceAccountPermissionGrant]
        pass

    @abstractmethod
    def service_account_grants_for_permission(self, name, argument=None):
        # type: (str, Optional[str]) -> List[ServiceAccountPermissionGrant]
        pass

    @abstractmethod
    def service_account_paginated_grants_for_permission(
        self,
        name,  # type: str
        pagination,  # type: Pagination[PermissionServiceAccountGrantSortKey]
        argument=None,  # type: Optional[str]
    ):
        # type: (...) -> PaginatedList[ServiceAccountPermissionGrant]
        pass

    @abstractmethod
    def service_account_has_permission(self, service, permission):
        # type: (str, str) -> bool
        pass

    @abstractmethod
    def user_has_permission(self, user, permission):
        # type: (str, str) -> bool
        pass


class UserRepository(metaclass=ABCMeta):
    """Abstract base class for user repositories."""

    @abstractmethod
    def all_users(self):
        # type: () -> Dict[str, User]
        pass

    @abstractmethod
    def disable_user(self, name):
        # type: (str) -> None
        pass

    @abstractmethod
    def user_exists(self, name):
        # type: (str) -> bool
        pass

    @abstractmethod
    def user_is_enabled(self, name):
        # type: (str) -> bool
        pass


class RepositoryFactory(metaclass=ABCMeta):
    """Abstract base class for repository factories."""

    @abstractmethod
    def create_audit_log_repository(self):
        # type: () -> AuditLogRepository
        pass

    @abstractmethod
    def create_checkpoint_repository(self):
        # type: () -> CheckpointRepository
        pass

    @abstractmethod
    def create_group_edge_repository(self):
        # type: () -> GroupEdgeRepository
        pass

    @abstractmethod
    def create_group_repository(self):
        # type: () -> GroupRepository
        pass

    @abstractmethod
    def create_group_request_repository(self):
        # type: () -> GroupRequestRepository
        pass

    @abstractmethod
    def create_permission_repository(self):
        # type: () -> PermissionRepository
        pass

    @abstractmethod
    def create_permission_grant_repository(self):
        # type: () -> PermissionGrantRepository
        pass

    @abstractmethod
    def create_schema_repository(self):
        # type: () -> SchemaRepository
        pass

    @abstractmethod
    def create_service_account_repository(self):
        # type: () -> ServiceAccountRepository
        pass

    @abstractmethod
    def create_transaction_repository(self):
        # type: () -> TransactionRepository
        pass

    @abstractmethod
    def create_user_repository(self):
        # type: () -> UserRepository
        pass
