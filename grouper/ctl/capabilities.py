from grouper.capabilities import Capabilities
from grouper.ctl.util import ensure_valid_username, make_session
from grouper.models import User


@ensure_valid_username
def capabilities_command(args):
    session = make_session()
    user = User.get(session, name=args.username)
    if not user:
        print "No such user %s" % args.username
        return

    capabilities = Capabilities(user.capabilities)

    if args.subcommand == "list":
        for key in Capabilities.words:
            if capabilities.has(key):
                print key
    elif args.subcommand == "add":
        print "Setting %s on user %s" % (args.capability, args.username)
        capabilities.set(args.capability)
        user.capabilities = capabilities.dump()
        session.commit()
    elif args.subcommand == "rm":
        print "Removing %s from user %s" % (args.capability, args.username)
        capabilities.clear(args.capability)
        user.capabilities = capabilities.dump()
        session.commit()


def add_parser(subparsers):
    capabilities_parser = subparsers.add_parser(
        "capabilities", help="Make a user an user or group admin.")
    capabilities_parser.set_defaults(func=capabilities_command)
    capabilities_subparser = capabilities_parser.add_subparsers(dest="subcommand")

    capabilities_list_parser = capabilities_subparser.add_parser(
        "list", help="List capabilities of a user.")
    capabilities_list_parser.add_argument("username")

    capabilities_add_parser = capabilities_subparser.add_parser(
        "add", help="Add capabilities to a user.")
    capabilities_add_parser.add_argument("username")
    capabilities_add_parser.add_argument("capability", choices=Capabilities.words.keys())

    capabilities_rm_parser = capabilities_subparser.add_parser(
        "rm", help="Remove capabilities from a user.")
    capabilities_rm_parser.add_argument("username")
    capabilities_rm_parser.add_argument("capability", choices=Capabilities.words.keys())
