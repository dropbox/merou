import logging
from typing import TYPE_CHECKING

from grouper.ctl.base import CtlCommand
from grouper.services.audit_log import AuditLogService
from grouper.services.permission import PermissionService
from grouper.usecases.disable_permission import DisablePermission, DisablePermissionUI

if TYPE_CHECKING:
    from argparse import _SubParsersAction, Namespace


class PermissionCommand(CtlCommand, DisablePermissionUI):
    """Commands to modify permissions."""

    def add_parser(self, subparsers):
        # type: (_SubParsersAction) -> None
        """Add the command-line options."""
        parser = subparsers.add_parser("permission", help="Manipulate permissions")
        parser.set_defaults(func=self.run)

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

    def disabled_permission(self, name):
        # type: (str) -> None
        logging.info("disabled permission %s", name)

    def disable_permission_failed_because_not_found(self, name):
        # type: (str) -> None
        logging.critical("permission %s not found", name)

    def disable_permission_failed_because_permission_denied(self, name):
        # type: (str) -> None
        logging.critical("not permitted to disable permission %s", name)

    def disable_permission_failed_because_system_permission(self, name):
        # type: (str) -> None
        logging.critical("cannot disable system permission %s", name)

    def run(self, args):
        # type: (Namespace) -> None
        """Run a permission command."""
        audit_log = AuditLogService(self.session)
        service = PermissionService(self.session, audit_log)
        usecase = DisablePermission(self.session, args.actor_name, self, service)
        usecase.disable_permission(args.name)
