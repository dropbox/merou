from typing import TYPE_CHECKING

from grouper.usecases.dump_schema import DumpSchemaUI

if TYPE_CHECKING:
    from tests.setup import SetupTest


class MockUI(DumpSchemaUI):
    def dumped_schema(self, schema):
        # type: (str) -> None
        self.schema = schema


def test_dump_schema(setup):
    # type: (SetupTest) -> None
    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_dump_schema_usecase(mock_ui)
    usecase.dump_schema()
    assert "service_account_permissions_map" in mock_ui.schema
