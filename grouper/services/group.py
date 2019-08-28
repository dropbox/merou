import re
from typing import TYPE_CHECKING

from grouper.constants import NAME_VALIDATION
from grouper.entities.group import InvalidGroupNameException
from grouper.usecases.interfaces import GroupInterface

if TYPE_CHECKING:
    from typing import List, Optional
    from grouper.entities.group import GroupJoinPolicy, MemberInfo
    from grouper.entities.group_request import UserGroupRequest
    from grouper.entities.permission_grant import GroupPermissionGrant
    from grouper.entities.permission_request import PermissionRequest
    from grouper.repositories.group import Group
    from grouper.repositories.interfaces import (
        GroupRepository,
        GroupEdgeRepository,
        GroupRequestRepository,
        PermissionRequestRepository,
        PermissionGrantRepository,
        ServiceAccountRepository,
    )


class GroupService(GroupInterface):
    """High-level logic to manipulate groups."""

    def __init__(
        self,
        group_repository,  # type: GroupRepository
        group_edge_repository,  # type: GroupEdgeRepository
        group_request_repository,  # type: GroupRequestRepository
        permission_grant_repository,  # type: PermissionGrantRepository
        permission_request_repository,  # type: PermissionRequestRepository
        service_account_repository,  # type: ServiceAccountRepository
    ):
        # type: (...) -> None
        self.group_repository = group_repository
        self.group_edge_repository = group_edge_repository
        self.group_request_repository = group_request_repository
        self.permission_grant_repository = permission_grant_repository
        self.permission_request_repository = permission_request_repository
        self.service_account_repository = service_account_repository

    def create_group(self, name, description, join_policy):
        # type: (str, str, GroupJoinPolicy) -> None
        if not self.is_valid_group_name(name):
            raise InvalidGroupNameException(name)
        self.group_repository.create_group(name, description, join_policy)

    def grant_permission_to_group(self, permission, argument, group):
        # type: (str, str, str) -> None
        self.permission_grant_repository.grant_permission_to_group(permission, argument, group)

    def group(self, name):
        # type: (str) -> Optional[Group]
        return self.group_repository.get_group(name)

    def group_exists(self, name):
        # type: (str) -> bool
        return bool(self.group_repository.get_group(name))

    def is_valid_group_name(self, name):
        # type: (str) -> bool
        return bool(re.match("^{}$".format(NAME_VALIDATION), name))

    def members_infos(self, name):
        # type: (str) -> List[MemberInfo]
        return self.group_edge_repository.group_members(name)

    def direct_parent_groups(self, name):
        # type: (str) -> List[str]
        return self.group_edge_repository.direct_parent_groups(name)

    def service_accounts(self, name):
        # type: (str) -> List[str]
        return self.service_account_repository.service_accounts_of_group(name)

    def pending_join_requests(self, groupname):
        # type: (str) -> List[UserGroupRequest]
        return self.group_request_repository.pending_requests_for_group(groupname)

    def permission_grants(self, groupname):
        # type: (str) -> List[GroupPermissionGrant]
        """Get the permission grants that a group has"""
        return self.permission_grant_repository.permission_grants_for_group(groupname)

    def pending_permission_grant_requests(self, groupname):
        # type: (str) -> List[PermissionRequest]
        return self.permission_request_repository.pending_requests_for_group(groupname)
