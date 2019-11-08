from __future__ import annotations

import csv
import logging
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

from grouper.ctl.util import argparse_validate_date, ensure_valid_groupname, ensure_valid_username
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.models.user import User
from grouper.plugin.exceptions import PluginRejectedGroupMembershipUpdate

if TYPE_CHECKING:
    from argparse import Namespace, _SubParsersAction
    from grouper.ctl.settings import CtlSettings
    from grouper.models.base.session import Session
    from grouper.repositories.factory import SessionFactory
    from typing import Iterator, IO


@ensure_valid_groupname
def group_command(args: Namespace, settings: CtlSettings, session_factory: SessionFactory) -> None:
    session = session_factory.create_session()
    group = session.query(Group).filter_by(groupname=args.groupname).scalar()
    if not group:
        logging.error("No such group %s", args.groupname)
        return

    if args.subcommand in ["add_member", "remove_member"]:
        # somewhat hacky: using function instance to use `ensure_valid_username` only on
        # these subcommands
        @ensure_valid_username
        def call_mutate(
            args: Namespace, settings: CtlSettings, session_factory: SessionFactory
        ) -> None:
            mutate_group_command(session, group, args)

        call_mutate(args, settings, session_factory)

    elif args.subcommand == "log_dump":
        logdump_group_command(session, group, args)


def mutate_group_command(session: Session, group: Group, args: Namespace) -> None:
    for username in args.username:
        user = User.get(session, name=username)
        if not user:
            logging.error("no such user '{}'".format(username))
            return

        if args.subcommand == "add_member":
            if args.member:
                role = "member"
            elif args.owner:
                role = "owner"
            elif args.np_owner:
                role = "np-owner"
            elif args.manager:
                role = "manager"

            assert role

            logging.info("Adding {} as {} to group {}".format(username, role, args.groupname))
            group.add_member(user, user, "grouper-ctl join", status="actioned", role=role)
            AuditLog.log(
                session,
                user.id,
                "join_group",
                "{} manually joined via grouper-ctl".format(username),
                on_group_id=group.id,
            )
            session.commit()

        elif args.subcommand == "remove_member":
            logging.info("Removing {} from group {}".format(username, args.groupname))

            try:
                group.revoke_member(user, user, "grouper-ctl remove")
                AuditLog.log(
                    session,
                    user.id,
                    "leave_group",
                    "{} manually left via grouper-ctl".format(username),
                    on_group_id=group.id,
                )
                session.commit()
            except PluginRejectedGroupMembershipUpdate as e:
                logging.error("%s", e)


@contextmanager
def open_file_or_stdout_for_write(fn: str) -> Iterator[IO[str]]:
    """mimic standard library `open` function to support stdout if None is
    specified as the filename."""
    if not fn or fn == "--":
        fh = sys.stdout
    else:
        fh = open(fn, "w")

    try:
        yield fh
    finally:
        if fh is not sys.stdout:
            fh.close()


def logdump_group_command(session: Session, group: Group, args: Namespace) -> None:
    log_entries = session.query(AuditLog).filter(
        AuditLog.on_group_id == group.id, AuditLog.log_time > args.start_date
    )

    if args.end_date:
        log_entries = log_entries.filter(AuditLog.log_time <= args.end_date)

    with open_file_or_stdout_for_write(args.outfile) as fh:
        csv_w = csv.writer(fh)
        for log_entry in log_entries:
            if log_entry.on_user:
                extra = "user: {}".format(log_entry.on_user.username)
            elif log_entry.on_group:
                extra = "group: {}".format(log_entry.on_group.groupname)
            else:
                extra = ""

            csv_w.writerow(
                [
                    log_entry.log_time,
                    log_entry.actor,
                    log_entry.description,
                    log_entry.action,
                    extra,
                ]
            )


def add_parser(subparsers: _SubParsersAction) -> None:
    group_parser = subparsers.add_parser("group", help="Edit groups and membership")
    group_parser.set_defaults(func=group_command)
    group_subparser = group_parser.add_subparsers(dest="subcommand")

    group_join_parser = group_subparser.add_parser("add_member", help="Join a user to a group")
    group_join_parser.add_argument("groupname")
    group_join_parser.add_argument("username", nargs="+")

    group_join_type_parser = group_join_parser.add_mutually_exclusive_group(required=True)
    group_join_type_parser.add_argument("--member", action="store_true")
    group_join_type_parser.add_argument("--owner", action="store_true")
    group_join_type_parser.add_argument("--np-owner", action="store_true")
    group_join_type_parser.add_argument("--manager", action="store_true")

    group_remove_parser = group_subparser.add_parser(
        "remove_member", help="Remove a user from a group"
    )
    group_remove_parser.add_argument("groupname")
    group_remove_parser.add_argument("username", nargs="+")

    group_logdump_parser = group_subparser.add_parser(
        "log_dump", help="dump activity log fo a group"
    )
    group_logdump_parser.add_argument("groupname")
    group_logdump_parser.add_argument("start_date", type=argparse_validate_date)
    group_logdump_parser.add_argument(
        "--end_date",
        type=argparse_validate_date,
        default=None,
        help="end of date trange to dump logs, today if not specified",
    )
    group_logdump_parser.add_argument(
        "--outfile", type=str, default=None, help="file to write results to, None if stdout"
    )
