from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from six import with_metaclass

if TYPE_CHECKING:
    from grouper.entities.group import Group, GroupJoinPolicy
    from grouper.entities.pagination import PaginatedList, Pagination
    from grouper.entities.permission import Permission
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        PermissionGrant,
        ServiceAccountPermissionGrant,
    )
    from grouper.repositories.audit_log import AuditLogRepository
    from grouper.repositories.checkpoint import CheckpointRepository
    from grouper.repositories.group_request import GroupRequestRepository
    from grouper.repositories.schema import SchemaRepository
    from grouper.repositories.service_account import ServiceAccountRepository
    from grouper.repositories.transaction import TransactionRepository
    from grouper.repositories.user import UserRepository
    from grouper.usecases.list_permissions import ListPermissionsSortKey
    from typing import List, Optional


class GroupRepository(with_metaclass(ABCMeta, object)):
    """Abstract base class for group repositories."""

    @abstractmethod
    def create_group(self, name, description, can_join):
        # type: (str, str, GroupJoinPolicy) -> None
        pass

    @abstractmethod
    def get_group(self, name):
        # type: (str) -> Optional[Group]
        pass


class GroupEdgeRepository(with_metaclass(ABCMeta, object)):
    """Abstract base class for group edge repositories."""

    @abstractmethod
    def groups_of_user(self, username):
        # type: (str) -> List[str]
        pass


class PermissionRepository(with_metaclass(ABCMeta, object)):
    """Abstract base class for permission repositories."""

    @abstractmethod
    def create_permission(self, name, description):
        # type: (str, str) -> None
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


class PermissionGrantRepository(with_metaclass(ABCMeta, object)):
    """Abstract base class for permission grant repositories."""

    @abstractmethod
    def grant_permission_to_group(self, group, permission, argument):
        # type: (str, str, str) -> None
        pass

    @abstractmethod
    def group_grants_for_permission(self, name):
        # type: (str) -> List[GroupPermissionGrant]
        pass

    @abstractmethod
    def permission_grants_for_user(self, user):
        # type: (str) -> List[PermissionGrant]
        pass

    @abstractmethod
    def service_account_grants_for_permission(self, name):
        # type: (str) -> List[ServiceAccountPermissionGrant]
        pass

    @abstractmethod
    def user_has_permission(self, user, permission):
        # type: (str, str) -> bool
        pass


class RepositoryFactory(with_metaclass(ABCMeta, object)):
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
