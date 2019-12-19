import logging
import sys
from typing import TYPE_CHECKING

from grouper import public_key
from grouper.ctl.base import CtlCommand
from grouper.ctl.util import ensure_valid_username
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.plugin.exceptions import PluginRejectedDisablingUser
from grouper.repositories.factory import SessionFactory
from grouper.role_user import disable_role_user, enable_role_user
from grouper.usecases.convert_user_to_service_account import ConvertUserToServiceAccountUI
from grouper.user import disable_user, enable_user, get_all_users
from grouper.user_metadata import set_user_metadata

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from grouper.ctl.settings import CtlSettings
    from grouper.usecases.factory import UseCaseFactory


@ensure_valid_username
def user_command(args, settings, session_factory):
    # type: (Namespace, CtlSettings, SessionFactory) -> None
    session = session_factory.create_session()

    if args.subcommand == "create":
        for username in args.username:
            user = User.get(session, name=username)
            if not user:
                logging.info("{}: No such user, creating...".format(username))
                user = User.get_or_create(session, username=username, role_user=args.role_user)
                session.commit()
            else:
                logging.info("{}: Already exists. Doing nothing.".format(username))
        return

    elif args.subcommand == "disable":
        for username in args.username:
            user = User.get(session, name=username)
            if not user:
                logging.info("{}: No such user. Doing nothing.".format(username))
            elif not user.enabled:
                logging.info("{}: User already disabled. Doing nothing.".format(username))
            else:
                logging.info("{}: User found, disabling...".format(username))
                try:
                    if user.role_user:
                        disable_role_user(session, user)
                    else:
                        disable_user(session, user)
                    AuditLog.log(
                        session,
                        user.id,
                        "disable_user",
                        "(Administrative) User disabled via grouper-ctl",
                        on_user_id=user.id,
                    )
                    session.commit()
                except PluginRejectedDisablingUser as e:
                    logging.error("%s", e)
                    sys.exit(1)

        return

    elif args.subcommand == "enable":
        for username in args.username:
            user = User.get(session, name=username)
            if not user:
                logging.info("{}: No such user. Doing nothing.".format(username))
            elif user.enabled:
                logging.info("{}: User not disabled. Doing nothing.".format(username))
            else:
                logging.info("{}: User found, enabling...".format(username))
                if user.role_user:
                    enable_role_user(
                        session, user, preserve_membership=args.preserve_membership, user=user
                    )
                else:
                    enable_user(session, user, user, preserve_membership=args.preserve_membership)
                AuditLog.log(
                    session,
                    user.id,
                    "enable_user",
                    "(Administrative) User enabled via grouper-ctl",
                    on_user_id=user.id,
                )
                session.commit()
        return

    # "add_public_key" and "set_metadata"
    user = User.get(session, name=args.username)
    if not user:
        logging.error("{}: No such user. Doing nothing.".format(args.username))
        return

    # User must exist at this point.

    if args.subcommand == "set_metadata":
        logging.info(
            "Setting %s metadata: %s=%s", args.username, args.metadata_key, args.metadata_value
        )
        if args.metadata_value == "":
            args.metadata_value = None
        set_user_metadata(session, user.id, args.metadata_key, args.metadata_value)
        session.commit()
    elif args.subcommand == "add_public_key":
        logging.info("Adding public key for user")

        try:
            pubkey = public_key.add_public_key(session, user, args.public_key)
        except public_key.DuplicateKey:
            logging.error("Key already in use")
            return
        except public_key.PublicKeyParseError:
            logging.error("Public key appears to be invalid")
            return

        AuditLog.log(
            session,
            user.id,
            "add_public_key",
            "(Administrative) Added public key: {}".format(pubkey.fingerprint_sha256),
            on_user_id=user.id,
        )


class ConvertUserToServiceAccountCommand(CtlCommand, ConvertUserToServiceAccountUI):
    """Convert a user to a service account."""

    @staticmethod
    def add_arguments(parser):
        # type: (ArgumentParser) -> None
        parser.add_argument(
            "--owner", required=True, help="Name of group to own the service account"
        )
        parser.add_argument("username")

    def __init__(self, usecase_factory):
        # type: (UseCaseFactory) -> None
        self.usecase_factory = usecase_factory

    def converted_user_to_service_account(self, user, owner):
        # type: (str, str) -> None
        logging.info("converted user %s to service account owned by %s", user, owner)

    def convert_user_to_service_account_failed_permission_denied(self, user):
        # type: (str) -> None
        logging.critical("not permitted to convert user %s to service account", user)
        sys.exit(1)

    def convert_user_to_service_account_failed_user_is_in_groups(self, user):
        # type: (str) -> None
        logging.critical("user %s cannot be converted while a member of any groups", user)
        sys.exit(1)

    def run(self, args):
        # type: (Namespace) -> None
        usecase = self.usecase_factory.create_convert_user_to_service_account_usecase(
            args.actor_name, self
        )
        usecase.convert_user_to_service_account(args.username, args.owner)


class UserCommand(CtlCommand):
    """Commands to modify users."""

    @staticmethod
    def add_arguments(parser):
        # type: (ArgumentParser) -> None
        parser.add_argument(
            "-a",
            "--actor",
            required=False,
            dest="actor_name",
            help=(
                "Name of the entity performing this action."
                " Must be a valid Grouper human or service account."
            ),
        )

        subparser = parser.add_subparsers(dest="subcommand")

        user_key_parser = subparser.add_parser("add_public_key", help="Add public key to user")
        user_key_parser.add_argument("username")
        user_key_parser.add_argument("public_key")

        user_convert_parser = subparser.add_parser(
            "convert_to_service_account", help="Convert to service account"
        )
        ConvertUserToServiceAccountCommand.add_arguments(user_convert_parser)

        user_create_parser = subparser.add_parser("create", help="Create a new user account")
        user_create_parser.add_argument("username", nargs="+")
        user_create_parser.add_argument(
            "--role-user",
            default=False,
            action="store_true",
            help="If given, identifies user as a role user.",
        )

        user_disable_parser = subparser.add_parser("disable", help="Disable a user account")
        user_disable_parser.add_argument("username", nargs="+")

        user_enable_parser = subparser.add_parser("enable", help="(Re-)enable a user account")
        user_enable_parser.add_argument("username", nargs="+")
        user_enable_parser.add_argument(
            "--preserve-membership",
            default=False,
            action="store_true",
            help="Unless provided, scrub all group memberships when re-enabling user.",
        )

        subparser.add_parser("list", help="List all users and their account statuses")

        user_set_metadata_parser = subparser.add_parser(
            "set_metadata", help="Set metadata on user"
        )
        user_set_metadata_parser.add_argument("username")
        user_set_metadata_parser.add_argument("metadata_key")
        user_set_metadata_parser.add_argument("metadata_value")

    def __init__(self, settings, usecase_factory):
        # type: (CtlSettings, UseCaseFactory) -> None
        self.settings = settings
        self.usecase_factory = usecase_factory

    def run(self, args):
        # type: (Namespace) -> None
        if args.subcommand == "convert_to_service_account":
            subcommand = ConvertUserToServiceAccountCommand(self.usecase_factory)
            subcommand.run(args)

        elif args.subcommand == "list":
            # Ugly temporary hack until this is converted to a usecase.
            repository_factory = self.usecase_factory.service_factory.repository_factory
            session = repository_factory.session_factory.create_session()
            all_users = get_all_users(session)
            for user in all_users:
                user_enabled = "enabled" if user.enabled else "disabled"
                logging.info("{} has status {}".format(user.name, user_enabled))
            return

        else:
            # Ugly temporary hack until this is converted to a usecase.
            repository_factory = self.usecase_factory.service_factory.repository_factory
            user_command(args, self.settings, repository_factory.session_factory)
