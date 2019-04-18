from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grouper.usecases.interfaces import SchemaInterface


class InitializeSchema(object):
    """Initialize the schema for a fresh database."""

    def __init__(self, schema_service):
        # type: (SchemaInterface) -> None
        self.schema_service = schema_service

    def initialize_schema(self):
        # type: () -> None
        self.schema_service.initialize_schema()
