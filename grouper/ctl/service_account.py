import logging
import sys
from typing import TYPE_CHECKING

from grouper.ctl.base import CtlCommand
from grouper.usecases.create_service_account import CreateServiceAccountUI

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from grouper.usecases.factory import UseCaseFactory


class CreateServiceAccountCommand(CtlCommand, CreateServiceAccountUI):
    """Command to create a service account."""

    @staticmethod
    def add_arguments(parser):
        # type: (ArgumentParser) -> None
        parser.add_argument("name", help="Name for the service account")
        parser.add_argument("owner", help="Name of the owner (must be a valid group)")
        parser.add_argument("machine_set", help="Machine set for the service account")
        parser.add_argument("description", help="Description for the service account")

    def __init__(self, usecase_factory):
        # type: (UseCaseFactory) -> None
        self.usecase_factory = usecase_factory

    def create_service_account_failed_already_exists(self, service, owner):
        # type: (str, str) -> None
        logging.critical("service account %s already exists", service)
        sys.exit(1)

    def create_service_account_failed_invalid_name(self, service, owner, message):
        # type: (str, str, str) -> None
        logging.critical("invalid service account name %s: %s", service, message)
        sys.exit(1)

    def create_service_account_failed_invalid_machine_set(
        self, service, owner, machine_set, message
    ):
        # type: (str, str, str, str) -> None
        logging.critical("machine set %s is not valid: %s", machine_set, message)
        sys.exit(1)

    def create_service_account_failed_invalid_owner(self, service, owner):
        # type: (str, str) -> None
        logging.critical("owning group %s does not exist", owner)
        sys.exit(1)

    def create_service_account_failed_permission_denied(self, service, owner):
        # type: (str, str) -> None
        logging.critical(
            "permission denied creating service account %s owned by %s", service, owner
        )
        sys.exit(1)

    def created_service_account(self, service, owner):
        # type: (str, str) -> None
        logging.info("created new service account %s owned by %s", service, owner)

    def run(self, args):
        # type: (Namespace) -> None
        usecase = self.usecase_factory.create_create_service_account_usecase(args.actor_name, self)
        usecase.create_service_account(args.name, args.owner, args.machine_set, args.description)


class ServiceAccountCommand(CtlCommand):
    """Commands to modify service accounts."""

    @staticmethod
    def add_arguments(parser):
        # type: (ArgumentParser) -> None
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
        parser = subparser.add_parser("create", help="Create a new service account")
        CreateServiceAccountCommand.add_arguments(parser)

    def __init__(self, usecase_factory):
        # type: (UseCaseFactory) -> None
        self.usecase_factory = usecase_factory

    def run(self, args):
        # type: (Namespace) -> None
        if args.subcommand == "create":
            subcommand = CreateServiceAccountCommand(self.usecase_factory)
            subcommand.run(args)
        else:
            raise ValueError("unknown subcommand {}".format(args.subcommand))
