from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from six import with_metaclass

if TYPE_CHECKING:
    from grouper.usecases.interfaces import SchemaInterface


class DumpSchemaUI(with_metaclass(ABCMeta, object)):
    """Abstract base class for UI for DumpSchema."""

    @abstractmethod
    def dumped_schema(self, schema):
        # type: (str) -> None
        pass


class DumpSchema(object):
    """Dump the database schema as a string."""

    def __init__(self, ui, schema_service):
        # type: (DumpSchemaUI, SchemaInterface) -> None
        self.ui = ui
        self.schema_service = schema_service

    def dump_schema(self):
        # type: () -> None
        schema = self.schema_service.dump_schema()
        self.ui.dumped_schema(schema)
