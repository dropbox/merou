from typing import TYPE_CHECKING

from grouper.ctl.permission import PermissionCommand

if TYPE_CHECKING:
    from argparse import _SubParsersAction
    from grouper.ctl.base import CtlCommand
    from grouper.usecases.factory import UseCaseFactory


class UnknownCommand(Exception):
    """Attempted to run a command with no known class."""

    pass


class CtlCommandFactory(object):
    """Construct and add parsers for grouper-ctl commands."""

    @staticmethod
    def add_all_parsers(subparsers):
        # type: (_SubParsersAction) -> None
        """Initialize parsers for all grouper-ctl commands.

        This is a static method since it has to be called before command-line parsing, but
        constructing a CtlCommandFactory requires a UseCaseFactory, which in turn requires
        information such as the database URL that may be overridden on the command line and thus
        cannot be created until after command-line parsing.
        """
        parser = subparsers.add_parser("permission", help="Manipulate permissions")
        PermissionCommand.add_arguments(parser)

    def __init__(self, usecase_factory):
        # type: (UseCaseFactory) -> None
        self.usecase_factory = usecase_factory

    def construct_command(self, command):
        # type: (str) -> CtlCommand
        if command == "permission":
            return self.construct_permission_command()
        else:
            raise UnknownCommand("unknown command {}".format(command))

    def construct_permission_command(self):
        # type: () -> PermissionCommand
        return PermissionCommand(self.usecase_factory)
