import re
from typing import TYPE_CHECKING

from grouper.constants import NAME_VALIDATION
from grouper.entities.group import GroupJoinPolicy, InvalidGroupNameException
from grouper.usecases.interfaces import GroupInterface

if TYPE_CHECKING:
    from grouper.repositories.interfaces import GroupRepository, PermissionGrantRepository


class GroupService(GroupInterface):
    """High-level logic to manipulate groups."""

    def __init__(self, group_repository, permission_grant_repository):
        # type: (GroupRepository, PermissionGrantRepository) -> None
        self.group_repository = group_repository
        self.permission_grant_repository = permission_grant_repository

    def create_group(self, name, description, join_policy):
        # type: (str, str, GroupJoinPolicy) -> None
        if not self.is_valid_group_name(name):
            raise InvalidGroupNameException(name)
        self.group_repository.create_group(name, description, join_policy)

    def grant_permission_to_group(self, permission, argument, group):
        # type: (str, str, str) -> None
        self.permission_grant_repository.grant_permission_to_group(permission, argument, group)

    def group_exists(self, name):
        # type: (str) -> bool
        return True if self.group_repository.get_group(name) else False

    def is_valid_group_name(self, name):
        # type: (str) -> bool
        return re.match("^{}$".format(NAME_VALIDATION), name) is not None
