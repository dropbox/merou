from typing import TYPE_CHECKING

from grouper.constants import (
    DEFAULT_ADMIN_GROUP,
    GROUP_ADMIN,
    PERMISSION_ADMIN,
    PERMISSION_AUDITOR,
    USER_ADMIN,
)
from grouper.entities.group import GroupJoinPolicy
from grouper.usecases.interfaces import GroupInterface

if TYPE_CHECKING:
    from grouper.repositories.interfaces import GroupRepository, PermissionGrantRepository
    from grouper.settings import Settings


class GroupService(GroupInterface):
    """High-level logic to manipulate groups."""

    def __init__(self, settings, group_repository, permission_grant_repository):
        # type: (Settings, GroupRepository, PermissionGrantRepository) -> None
        self.settings = settings
        self.group_repository = group_repository
        self.permission_grant_repository = permission_grant_repository

    def create_group(self, name, description, join_policy):
        # type: (str, str, GroupJoinPolicy) -> None
        self.group_repository.create_group(name, description, join_policy)

    def grant_permission_to_group(self, permission, argument, group):
        # type: (str, str, str) -> None
        self.permission_grant_repository.grant_permission_to_group(permission, argument, group)

    def group_exists(self, name):
        # type: (str) -> bool
        return True if self.group_repository.get_group(name) else False

    def initialize_administrator_group(self):
        # type: () -> None
        if not self.group_exists(DEFAULT_ADMIN_GROUP):
            self.create_group(
                DEFAULT_ADMIN_GROUP, "Administrators of the Grouper system", GroupJoinPolicy.NOBODY
            )
            for permission in (GROUP_ADMIN, PERMISSION_ADMIN, USER_ADMIN):
                self.grant_permission_to_group(permission, "", DEFAULT_ADMIN_GROUP)

    def initialize_auditors_group(self):
        # type: () -> None
        if not self.settings.auditors_group:
            return
        if not self.group_exists(self.settings.auditors_group):
            self.create_group(
                self.settings.auditors_group,
                "Allows members to own groups with audited permissions",
                GroupJoinPolicy.CAN_ASK,
            )
            self.grant_permission_to_group(PERMISSION_AUDITOR, "", self.settings.auditors_group)
