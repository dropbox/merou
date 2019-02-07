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
    from grouper.usecases.authorization import Authorization


class PermissionNotFoundException(Exception):
    """Attempt to operate on a permission not found in the storage layer."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "Permission {} not found".format(name)
        super(PermissionNotFoundException, self).__init__(msg)


class PermissionInterface(object):
    """Abstract base class for permission storage layer."""

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
    def user_is_permission_admin(self, user_name):
        # type: (str) -> bool
        pass
