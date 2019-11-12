from typing import TYPE_CHECKING

from grouper.constants import (
    DEFAULT_ADMIN_GROUP,
    GROUP_ADMIN,
    PERMISSION_ADMIN,
    PERMISSION_AUDITOR,
    USER_ADMIN,
)
from grouper.entities.group import GroupJoinPolicy

if TYPE_CHECKING:
    from grouper.settings import Settings
    from grouper.usecases.interfaces import GroupInterface
    from grouper.usecases.interfaces import PermissionInterface
    from grouper.usecases.interfaces import SchemaInterface
    from grouper.usecases.interfaces import TransactionInterface


class InitializeSchema:
    """Initialize the schema for a fresh database."""

    def __init__(
        self,
        settings,  # type: Settings
        schema_service,  # type: SchemaInterface
        group_service,  # type: GroupInterface
        permission_service,  # type: PermissionInterface
        transaction_service,  # type: TransactionInterface
    ):
        # type: (...) -> None
        self.settings = settings
        self.schema_service = schema_service
        self.group_service = group_service
        self.permission_service = permission_service
        self.transaction_service = transaction_service

    def initialize_schema(self):
        # type: () -> None
        self.schema_service.initialize_schema()
        with self.transaction_service.transaction():
            self.permission_service.create_system_permissions()
            if not self.group_service.group_exists(DEFAULT_ADMIN_GROUP):
                self.group_service.create_group(
                    DEFAULT_ADMIN_GROUP,
                    "Administrators of the Grouper system",
                    GroupJoinPolicy.NOBODY,
                )
                for permission in (GROUP_ADMIN, PERMISSION_ADMIN, USER_ADMIN):
                    self.group_service.grant_permission_to_group(
                        permission, "", DEFAULT_ADMIN_GROUP
                    )
            if self.settings.auditors_group:
                if not self.group_service.group_exists(self.settings.auditors_group):
                    self.group_service.create_group(
                        self.settings.auditors_group,
                        "Allows members to own groups with audited permissions",
                        GroupJoinPolicy.CAN_ASK,
                    )
                    self.group_service.grant_permission_to_group(
                        PERMISSION_AUDITOR, "", self.settings.auditors_group
                    )
