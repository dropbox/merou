"""Interfaces used by use cases to talk to backend services.

Defines general interfaces to use to talk to backend application services (storage, authorization,
user, group, permission, and so forth) that are shared among multiple use cases.  Also defines the
exceptions they throw, if needed.

Do not define UI interfaces to talk to frontends here.  There should be a one-to-one correspondance
between UI interfaces and use cases, so the UI interface is defined in the same file with the use
case.

By convention, all class names here end in Interface or Exception.
"""

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grouper.entities.pagination import PaginatedList, Pagination
    from grouper.entities.permission import Permission
    from grouper.usecases.authorization import Authorization
    from grouper.usecases.list_permissions import ListPermissionsSortKey


class PermissionInterface(object):
    """Abstract base class for permission operations and queries."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def disable_permission(self, name, authorization):
        # type: (str, Authorization) -> None
        pass

    @abstractmethod
    def is_system_permission(self, name):
        # type: (str) -> bool
        pass

    @abstractmethod
    def list_permissions(self, pagination, audited_only):
        # type: (Pagination[ListPermissionsSortKey], bool) -> PaginatedList[Permission]
        pass


class TransactionInterface(object):
    """Abstract base class for starting and committing transactions."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def start_transaction(self):
        # type: () -> None
        pass

    @abstractmethod
    def commit(self):
        # type: () -> None
        pass


class ServiceFactoryInterface(object):
    """Abstract base class for creating services."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def create_permission_service(self):
        # type: () -> PermissionInterface
        pass


class UserInterface(object):
    """Abstract base class for user operations and queries."""

    __metaclass__ = ABCMeta

    @abstractmethod
    def user_can_create_permissions(self, user):
        # type: (str) -> bool
        pass

    @abstractmethod
    def user_is_permission_admin(self, user):
        # type: (str) -> bool
        pass
