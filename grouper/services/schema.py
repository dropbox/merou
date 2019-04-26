from typing import TYPE_CHECKING

from grouper.usecases.interfaces import SchemaInterface

if TYPE_CHECKING:
    from grouper.repositories.schema import SchemaRepository


class SchemaService(SchemaInterface):
    """Manage the schema of the storage layer."""

    def __init__(self, schema_repository):
        # type: (SchemaRepository) -> None
        self.schema_repository = schema_repository

    def dump_schema(self):
        # type: () -> str
        return self.schema_repository.dump_schema()

    def initialize_schema(self):
        # type: () -> None
        self.schema_repository.initialize_schema()
