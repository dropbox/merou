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

from six import with_metaclass

if TYPE_CHECKING:
    from datetime import datetime
    from grouper.entities.audit import GroupAuditDetails, GroupAuditInfo
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.entities.group import Group, GroupAccess, GroupJoinPolicy, MemberInfo
    from grouper.entities.group_request import GroupRequestStatus, UserGroupRequest
    from grouper.entities.pagination import PaginatedList, Pagination
    from grouper.entities.permission import Permission, PermissionAccess
    from grouper.entities.permission_grant import (
        GrantablePermission,
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
        UniqueGrantsOfPermission,
    )
    from grouper.entities.permission_request import PermissionRequest
    from grouper.entities.user import User
    from grouper.usecases.authorization import Authorization
    from grouper.usecases.list_permissions import ListPermissionsSortKey
    from typing import ContextManager, Dict, List, Optional, Tuple


class AuditInterface(with_metaclass(ABCMeta, object)):
    """Abstract base class for audits."""

    @abstractmethod
    def is_group_audited(self, groupname):
        # type: (str) -> bool
        pass

    @abstractmethod
    def group_pending_audit_info(self, groupname):
        # type: (str) -> Optional[GroupAuditInfo]
        """Return high-level information about a pending audit for a group, if any"""
        pass

    @abstractmethod
    def group_pending_audit_details(self, groupname):
        # type: (str) -> Optional[GroupAuditDetails]
        """Return detail information about a pending audit for a group, if any"""
        pass


class AuditLogInterface(with_metaclass(ABCMeta, object)):
    """Abstract base class for the audit log.

    The date parameter to the log methods is primarily for use in tests, where to get a consistent
    sort order the audit log entries may need to be spaced out over time.  If not set, the default
    is the current time.
    """

    @abstractmethod
    def entries_affecting_group(self, group, limit):
        # type: (str, int) -> List[AuditLogEntry]
        pass

    @abstractmethod
    def entries_affecting_permission(self, permission, limit):
        # type: (str, int) -> List[AuditLogEntry]
        pass

    @abstractmethod
    def entries_affecting_user(self, user, limit):
        # type: (str, int) -> List[AuditLogEntry]
        pass

    @abstractmethod
    def log_create_service_account(self, service, owner, authorization, date=None):
        # type: (str, str, Authorization, Optional[datetime]) -> None
        pass

    @abstractmethod
    def log_create_service_account_from_disabled_user(self, user, authorization, date=None):
        # type: (str, Authorization, Optional[datetime]) -> None
        pass

    @abstractmethod
    def log_create_permission(self, permission, authorization, date=None):
        # type: (str, Authorization, Optional[datetime]) -> None
        pass

    @abstractmethod
    def log_disable_permission(self, permission, authorization, date=None):
        # type: (str, Authorization, Optional[datetime]) -> None
        pass

    @abstractmethod
    def log_disable_user(self, username, authorization, date=None):
        # type: (str, Authorization, Optional[datetime]) -> None
        pass

    @abstractmethod
    def log_enable_service_account(self, user, owner, authorization, date=None):
        # type: (str, str, Authorization, Optional[datetime]) -> None
        pass

    @abstractmethod
    def log_revoke_group_permission_grant(
        self,
        group,  # type: str
        permission,  # type: str
        argument,  # type: str
        authorization,  # type: Authorization
        date=None,  # type: Optional[datetime]
    ):
        # type: (...) -> None
        pass

    @abstractmethod
    def log_revoke_service_account_permission_grant(
        self,
        service_account,  # type: str
        permission,  # type: str
        argument,  # type: str
        authorization,  # type: Authorization
        date=None,  # type: Optional[datetime]
    ):
        # type: (...) -> None
        pass

    @abstractmethod
    def log_user_group_request_status_change(self, request, status, authorization, date=None):
        # type: (UserGroupRequest, GroupRequestStatus, Authorization, Optional[datetime]) -> None
        pass


class GroupInterface(with_metaclass(ABCMeta, object)):
    """Abstract base class for group operations and queries."""

    @abstractmethod
    def create_group(self, name, description, join_policy):
        # type: (str, str, GroupJoinPolicy) -> None
        pass

    @abstractmethod
    def grant_permission_to_group(self, permission, argument, group):
        # type: (str, str, str) -> None
        pass

    @abstractmethod
    def group(self, name):
        # type: (str) -> Optional[Group]
        pass

    @abstractmethod
    def group_exists(self, name):
        # type: (str) -> bool
        pass

    @abstractmethod
    def is_valid_group_name(self, name):
        # type: (str) -> bool
        pass

    @abstractmethod
    def members_infos(self, name):
        # type: (str) -> List[MemberInfo]
        pass

    @abstractmethod
    def direct_parent_groups(self, name):
        # type: (str) -> List[str]
        pass

    @abstractmethod
    def service_accounts(self, name):
        # type: (str) -> List[str]
        pass

    @abstractmethod
    def pending_join_requests(self, groupname):
        # type: (str) -> List[UserGroupRequest]
        """Get the pending requests to join a group

        Arg(s):
            groupname: The group in question

        Return:
            List of UserGroupRequest
        """
        pass

    @abstractmethod
    def permission_grants(self, groupname):
        # type: (str) -> List[GroupPermissionGrant]
        pass

    @abstractmethod
    def pending_permission_grant_requests(self, groupname):
        # type: (str) -> List[PermissionRequest]
        pass


class GroupRequestInterface(with_metaclass(ABCMeta, object)):
    """Abstract base class for requests for group membership."""

    @abstractmethod
    def cancel_all_requests_for_user(self, user, reason, authorization):
        # type: (str, str, Authorization) -> None
        pass


class PermissionInterface(with_metaclass(ABCMeta, object)):
    """Abstract base class for permission operations and queries."""

    @abstractmethod
    def all_grants(self):
        # type: () -> Dict[str, UniqueGrantsOfPermission]
        pass

    @abstractmethod
    def all_grants_of_permission(self, permission):
        # type: (str) -> UniqueGrantsOfPermission
        pass

    @abstractmethod
    def create_permission(self, name, description=""):
        # type: (str, str) -> None
        pass

    @abstractmethod
    def create_system_permissions(self):
        # type: () -> None
        pass

    @abstractmethod
    def disable_permission_and_revoke_grants(self, name, authorization):
        # type: (str, Authorization) -> None
        pass

    @abstractmethod
    def group_grants_for_permission(self, name):
        # type: (str) -> List[GroupPermissionGrant]
        pass

    @abstractmethod
    def service_account_grants_for_permission(self, name):
        # type: (str) -> List[ServiceAccountPermissionGrant]
        pass

    @abstractmethod
    def is_system_permission(self, name):
        # type: (str) -> bool
        pass

    @abstractmethod
    def list_permissions(self, pagination, audited_only):
        # type: (Pagination[ListPermissionsSortKey], bool) -> PaginatedList[Permission]
        pass

    @abstractmethod
    def permission(self, name):
        # type: (str) -> Optional[Permission]
        pass

    @abstractmethod
    def permission_exists(self, name):
        # type: (str) -> bool
        pass

    @abstractmethod
    def groups_that_can_approve_grant(self, grant):
        # type: (GrantablePermission) -> List[str]
        """Get names of groups that have permission to grant/revoke the given permission grant.

        Note that this permission to grant/revoke is not inherited: e.g., if `parent-group` has the
        permission to grant permission grant P, then a sub-group of `parent-group` can't
        grant/revoke permission grant P simply by virtue of being a sub-group of `parent-group`.
        """
        pass


class SchemaInterface(with_metaclass(ABCMeta, object)):
    """Abstract base class for low-level schema manipulation."""

    @abstractmethod
    def dump_schema(self):
        # type: () -> str
        pass

    @abstractmethod
    def initialize_schema(self):
        # type: () -> None
        pass


class ServiceAccountInterface(with_metaclass(ABCMeta, object)):
    """Abstract base class for service account operations and queries."""

    @abstractmethod
    def create_service_account(self, service, owner, machine_set, description, authorization):
        # type: (str, str, str, str, Authorization) -> None
        pass

    @abstractmethod
    def create_service_account_from_disabled_user(self, user, authorization):
        # type: (str, Authorization) -> None
        pass

    @abstractmethod
    def enable_service_account(self, user, owner, authorization):
        # type: (str, str, Authorization) -> None
        pass

    @abstractmethod
    def is_valid_service_account_name(self, name):
        # type: (str) -> Tuple[bool, Optional[str]]
        pass

    @abstractmethod
    def permission_grants_for_service_account(self, user):
        # type: (str) -> List[ServiceAccountPermissionGrant]
        pass

    @abstractmethod
    def service_account_exists(self, service):
        # type: (str) -> bool
        pass

    @abstractmethod
    def service_account_is_user_admin(self, user):
        # type: (str) -> bool
        pass


class TransactionInterface(with_metaclass(ABCMeta, object)):
    """Abstract base class for starting and committing transactions."""

    def transaction(self):
        # type: () -> ContextManager[None]
        pass


class UserInterface(with_metaclass(ABCMeta, object)):
    """Abstract base class for user operations and queries."""

    @abstractmethod
    def all_users(self):
        # type: () -> Dict[str, User]
        pass

    @abstractmethod
    def disable_user(self, user, authorization):
        # type: (str, Authorization) -> None
        pass

    @abstractmethod
    def group_access_for_user(self, user, group):
        # type: (str, str) -> GroupAccess
        pass

    @abstractmethod
    def groups_of_user(self, user):
        # type: (str) -> List[str]
        pass

    @abstractmethod
    def is_group_owner(self, user, group):
        # type: (str, str) -> bool
        pass

    @abstractmethod
    def direct_groups_of_user(self, user):
        # type: (str) -> List[str]
        pass

    @abstractmethod
    def permission_access_for_user(self, user, permission):
        # type: (str, str) -> PermissionAccess
        pass

    @abstractmethod
    def permission_grants_for_user(self, user):
        # type: (str) -> List[GroupPermissionGrant]
        pass

    @abstractmethod
    def user_can_create_permissions(self, user):
        # type: (str) -> bool
        pass

    @abstractmethod
    def user_exists(self, user):
        # type: (str) -> bool
        pass

    @abstractmethod
    def user_is_auditor(self, user):
        # type: (str) -> bool
        pass

    @abstractmethod
    def user_is_permission_admin(self, user):
        # type: (str) -> bool
        pass

    @abstractmethod
    def user_is_user_admin(self, user):
        # type: (str) -> bool
        pass

    @abstractmethod
    def user_can_grant_some_permissions(self, user):
        # type: (str) -> bool
        """Whether the user can grant (and revoke) *some* permission grant"""
        pass
