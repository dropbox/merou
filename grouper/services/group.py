import re
from typing import TYPE_CHECKING

from grouper.constants import NAME_VALIDATION
from grouper.entities.group import GroupJoinPolicy, InvalidGroupNameException
from grouper.usecases.interfaces import GroupInterface
from grouper.util import matches_glob

if TYPE_CHECKING:
    from grouper.entities.permission_grant import GroupPermissionGrant
    from grouper.repositories.group import GroupRepository
    from grouper.repositories.interfaces import PermissionGrantRepository
    from typing import List, Optional


class GroupService(GroupInterface):
    """High-level logic to manipulate groups."""

    def __init__(self, group_repository, permission_grant_repository):
        # type: (GroupRepository, PermissionGrantRepository) -> None
        self.group_repository = group_repository
        self.permission_grant_repository = permission_grant_repository

    def create_group(self, name, description, join_policy, email=None):
        # type: (str, str, GroupJoinPolicy, Optional[str]) -> None
        if not self.is_valid_group_name(name):
            raise InvalidGroupNameException(name)
        self.group_repository.create_group(name, description, join_policy, email)

    def group_has_matching_permission_grant(self, group, permission, argument):
        # type: (str, str, str) -> bool
        grants = self.permission_grant_repository.permission_grants_for_group(group)
        for grant in grants:
            if grant.permission == permission:
                if matches_glob(grant.argument, argument):
                    return True
        return False

    def grant_permission_to_group(self, permission, argument, group):
        # type: (str, str, str) -> None
        self.permission_grant_repository.grant_permission_to_group(permission, argument, group)

    def group_exists(self, name):
        # type: (str) -> bool
        return True if self.group_repository.get_group(name) else False

    def is_valid_group_name(self, name):
        # type: (str) -> bool
        return re.match("^{}$".format(NAME_VALIDATION), name) is not None

    def permission_grants_for_group(self, name):
        # type: (str) -> List[GroupPermissionGrant]
        return self.permission_grant_repository.permission_grants_for_group(name)
