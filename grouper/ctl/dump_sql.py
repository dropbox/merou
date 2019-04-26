from __future__ import print_function

from typing import TYPE_CHECKING

from grouper.ctl.base import CtlCommand
from grouper.usecases.dump_schema import DumpSchemaUI

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from grouper.usecases.factory import UseCaseFactory


class DumpSqlCommand(CtlCommand, DumpSchemaUI):
    """Commands to dump the database schema."""

    @staticmethod
    def add_arguments(parser):
        # type: (ArgumentParser) -> None
        return

    def __init__(self, usecase_factory):
        # type: (UseCaseFactory) -> None
        self.usecase_factory = usecase_factory

    def dumped_schema(self, schema):
        # type: (str) -> None
        print(schema)

    def run(self, args):
        # type: (Namespace) -> None
        usecase = self.usecase_factory.create_dump_schema_usecase(self)
        usecase.dump_schema()
