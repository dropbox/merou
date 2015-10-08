from grouper.ctl.util import ensure_valid_username, ensure_valid_groupname, make_session
from grouper.models import AuditLog, Group, User


@ensure_valid_username
@ensure_valid_groupname
def group_command(args):
    session = make_session()
    group = session.query(Group).filter_by(groupname=args.groupname).scalar()
    if not group:
        print "No such group %s" % args.groupname
        return

    user = User.get(session, name=args.username)
    if not user:
        print "no such user '{}'".format(args.username)
        return

    if args.subcommand == "add_member":
        print "Adding %s to group %s" % (args.username, args.groupname)
        group.add_member(user, user, "grouper-ctl join", status="actioned")
        AuditLog.log(
            session, user.id, 'join_group',
            '{} manually joined via grouper-ctl'.format(args.username),
            on_group_id=group.id)
        session.commit()

    elif args.subcommand == "remove_member":
        print "Removing %s from group %s" % (args.username, args.groupname)
        group.revoke_member(user, user, "grouper-ctl remove")
        AuditLog.log(
            session, user.id, 'leave_group',
            '{} manually left via grouper-ctl'.format(args.username),
            on_group_id=group.id)
        session.commit()

def add_parser(subparsers):
    group_parser = subparsers.add_parser(
        "group", help="Edit groups and membership")
    group_parser.set_defaults(func=group_command)
    group_subparser = group_parser.add_subparsers(dest="subcommand")

    group_join_parser = group_subparser.add_parser(
        "add_member", help="Join a user to a group")
    group_join_parser.add_argument("groupname")
    group_join_parser.add_argument("username")

    group_remove_parser = group_subparser.add_parser(
        "remove_member", help="Remove a user from a group")
    group_remove_parser.add_argument("groupname")
    group_remove_parser.add_argument("username")
