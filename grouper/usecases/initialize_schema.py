from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grouper.usecases.interfaces import GroupInterface
    from grouper.usecases.interfaces import PermissionInterface
    from grouper.usecases.interfaces import SchemaInterface
    from grouper.usecases.interfaces import TransactionInterface


class InitializeSchema(object):
    """Initialize the schema for a fresh database."""

    def __init__(
        self,
        schema_service,  # type: SchemaInterface
        group_service,  # type: GroupInterface
        permission_service,  # type: PermissionInterface
        transaction_service,  # type: TransactionInterface
    ):
        # type: (...) -> None
        self.schema_service = schema_service
        self.group_service = group_service
        self.permission_service = permission_service
        self.transaction_service = transaction_service

    def initialize_schema(self):
        # type: () -> None
        self.schema_service.initialize_schema()
        with self.transaction_service.transaction():
            self.permission_service.create_system_permissions()
            self.group_service.initialize_administrator_group()
            self.group_service.initialize_auditors_group()
