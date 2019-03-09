from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grouper.entities.pagination import PaginatedList, Pagination
    from grouper.entities.permission import Permission
    from grouper.entities.permission_grant import PermissionGrant
    from grouper.repositories.audit_log import AuditLogRepository
    from grouper.repositories.checkpoint import CheckpointRepository
    from grouper.repositories.transaction import TransactionRepository
    from grouper.usecases.list_permissions import ListPermissionsSortKey
    from typing import List, Optional


class PermissionRepository(object):
    """Abstract base class for permission repositories."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def get_permission(self, name):
        # type: (str) -> Optional[Permission]
        pass

    @abstractmethod
    def disable_permission(self, name):
        # type: (str) -> None
        pass

    @abstractmethod
    def list_permissions(self, pagination, audited_only):
        # type: (Pagination[ListPermissionsSortKey], bool) -> PaginatedList[Permission]
        pass


class PermissionGrantRepository(object):
    """Abstract base class for permission grants."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def permission_grants_for_user(self, user):
        # type: (str) -> List[PermissionGrant]
        pass

    @abstractmethod
    def user_has_permission(self, user, permission):
        # type: (str, str) -> bool
        pass


class RepositoryFactory(object):
    """Abstract base class for repository factories."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def create_audit_log_repository(self):
        # type: () -> AuditLogRepository
        pass

    @abstractmethod
    def create_checkpoint_repository(self):
        # type: () -> CheckpointRepository
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
    def create_transaction_repository(self):
        # type: () -> TransactionRepository
        pass
