from typing import TYPE_CHECKING

from grouper.ctl.base import CtlCommand

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from grouper.ctl.settings import CtlSettings
    from grouper.usecases.factory import UseCaseFactory


class SyncDbCommand(CtlCommand):
    """Commands to initialize the database."""

    @staticmethod
    def add_arguments(parser):
        # type: (ArgumentParser) -> None
        return

    def __init__(self, settings, usecase_factory):
        # type: (CtlSettings, UseCaseFactory) -> None
        self.settings = settings
        self.usecase_factory = usecase_factory

    def run(self, args):
        # type: (Namespace) -> None
        usecase = self.usecase_factory.create_initialize_schema_usecase()
        usecase.initialize_schema()
