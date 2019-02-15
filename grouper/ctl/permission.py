import logging
import sys
from typing import TYPE_CHECKING

from grouper.ctl.base import CtlCommand
from grouper.usecases.disable_permission import DisablePermissionUI

if TYPE_CHECKING:
    from argparse import _SubParsersAction, Namespace


class PermissionCommand(CtlCommand, DisablePermissionUI):
    """Commands to modify permissions."""

    @staticmethod
    def add_parser(subparsers):
        # type: (_SubParsersAction) -> str
        parser = subparsers.add_parser("permission", help="Manipulate permissions")

        parser.add_argument(
            "-a",
            "--actor",
            required=True,
            dest="actor_name",
            help=(
                "Name of the entity performing this action."
                " Must be a valid Grouper human or service account."
            ),
        )

        subparser = parser.add_subparsers(dest="subcommand")
        disable_parser = subparser.add_parser("disable", help="Disable a permission")
        disable_parser.add_argument("name", help="Name of permission to disable")

        return "permission"

    def disabled_permission(self, name):
        # type: (str) -> None
        logging.info("disabled permission %s", name)

    def disable_permission_failed_because_not_found(self, name):
        # type: (str) -> None
        logging.critical("permission %s not found", name)
        sys.exit(1)

    def disable_permission_failed_because_permission_denied(self, name):
        # type: (str) -> None
        logging.critical("not permitted to disable permission %s", name)
        sys.exit(1)

    def disable_permission_failed_because_system_permission(self, name):
        # type: (str) -> None
        logging.critical("cannot disable system permission %s", name)
        sys.exit(1)

    def run(self, args):
        # type: (Namespace) -> None
        """Run a permission command."""
        usecase = self.usecase_factory.create_disable_permission_usecase(args.actor_name, self)
        usecase.disable_permission(args.name)
