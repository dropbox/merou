from typing import TYPE_CHECKING

from grouper.ctl.dump_sql import DumpSqlCommand
from grouper.ctl.permission import PermissionCommand
from grouper.ctl.service_account import ServiceAccountCommand
from grouper.ctl.sync_db import SyncDbCommand
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


class CtlCommandFactory:
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
        parser = subparsers.add_parser("dump_sql", help="Dump database schema")
        DumpSqlCommand.add_arguments(parser)
        parser = subparsers.add_parser("permission", help="Manipulate permissions")
        PermissionCommand.add_arguments(parser)
        parser = subparsers.add_parser("service_account", help="Manipulate service accounts")
        ServiceAccountCommand.add_arguments(parser)
        parser = subparsers.add_parser("sync_db", help="Create database schema")
        SyncDbCommand.add_arguments(parser)
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
        if command == "dump_sql":
            return self.construct_dump_sql_command()
        elif command == "permission":
            return self.construct_permission_command()
        elif command == "service_account":
            return self.construct_service_account_command()
        elif command == "sync_db":
            return self.construct_sync_db_command()
        elif command == "user":
            return self.construct_user_command()
        elif command == "user_proxy":
            return self.construct_user_proxy_command()
        else:
            raise UnknownCommand("unknown command {}".format(command))

    def construct_dump_sql_command(self):
        # type: () -> DumpSqlCommand
        return DumpSqlCommand(self.usecase_factory)

    def construct_permission_command(self):
        # type: () -> PermissionCommand
        return PermissionCommand(self.usecase_factory)

    def construct_service_account_command(self):
        # type: () -> ServiceAccountCommand
        return ServiceAccountCommand(self.usecase_factory)

    def construct_sync_db_command(self):
        # type: () -> SyncDbCommand
        return SyncDbCommand(self.usecase_factory)

    def construct_user_command(self):
        # type: () -> UserCommand
        return UserCommand(self.settings, self.usecase_factory)

    def construct_user_proxy_command(self):
        # type: () -> UserProxyCommand
        return UserProxyCommand(self.settings)
