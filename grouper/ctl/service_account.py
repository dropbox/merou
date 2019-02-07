import logging

from grouper.ctl.util import ensure_valid_service_account_name, make_session
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount
from grouper.models.user import User
from grouper.service_account import create_service_account


@ensure_valid_service_account_name
def service_account_command(args):
    session = make_session()
    actor_user = User.get(session, name=args.actor_name)
    if not actor_user:
        logging.fatal('Actor user "{}" is not a valid Grouper user'.format(args.actor_name))
        return

    if args.subcommand == "create":
        name = args.name
        if ServiceAccount.get(session, name=name):
            logging.info("{}: Already exists. Doing nothing.".format(name))
            return
        owner_group = Group.get(session, name=args.owner_group)
        if not owner_group:
            logging.fatal('Owner group "{}" does not exist.'.format(args.owner_group))
            return
        logging.info("{}: No such service account, creating...".format(name))
        description = args.description
        machine_set = args.machine_set
        create_service_account(session, actor_user, name, description, machine_set, owner_group)
        return


def add_parser(subparsers):
    service_account_parser = subparsers.add_parser("service_account", help="Edit service account")
    service_account_parser.set_defaults(func=service_account_command)
    service_account_subparser = service_account_parser.add_subparsers(dest="subcommand")

    required_options_group = service_account_parser.add_argument_group("required named arguments")
    required_options_group.add_argument(
        "-a",
        "--actor",
        required=True,
        dest="actor_name",
        help=(
            "Name of the entity performing this action. "
            "Must be a valid Grouper human or service "
            "account."
        ),
    )

    service_account_create_parser = service_account_subparser.add_parser(
        "create", help="Create a new service account"
    )
    service_account_create_parser.add_argument("name", help=("Name for the service account"))
    service_account_create_parser.add_argument(
        "owner_group", help=("Name of the owner group. Must be a valid " "Grouper group")
    )
    service_account_create_parser.add_argument(
        "machine_set", help=("The machine set for the service account")
    )
    service_account_create_parser.add_argument(
        "description", help=("Description for the service account")
    )
