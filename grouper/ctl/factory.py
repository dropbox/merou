from typing import TYPE_CHECKING

from grouper.ctl.permission import PermissionCommand
from grouper.ctl.user import UserCommand
from grouper.ctl.user_proxy import UserProxyCommand

if TYPE_CHECKING:
    from argparse import _SubParsersAction
    from grouper.ctl.base import CtlCommand
    from grouper.ctl.settings import CtlSettings
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
        parser = subparsers.add_parser("user", help="Manipulate users")
        UserCommand.add_arguments(parser)
        parser = subparsers.add_parser("user_proxy", help="Start a development reverse proxy")
        UserProxyCommand.add_arguments(parser)

    def __init__(self, settings, usecase_factory):
        # type: (CtlSettings, UseCaseFactory) -> None
        self.settings = settings
        self.usecase_factory = usecase_factory

    def construct_command(self, command):
        # type: (str) -> CtlCommand
        if command == "permission":
            return self.construct_permission_command()
        elif command == "user":
            return self.construct_user_command()
        elif command == "user_proxy":
            return self.construct_user_proxy_command()
        else:
            raise UnknownCommand("unknown command {}".format(command))

    def construct_permission_command(self):
        # type: () -> PermissionCommand
        return PermissionCommand(self.usecase_factory)

    def construct_user_command(self):
        # type: () -> UserCommand
        return UserCommand(self.settings, self.usecase_factory)

    def construct_user_proxy_command(self):
        # type: () -> UserProxyCommand
        return UserProxyCommand()
