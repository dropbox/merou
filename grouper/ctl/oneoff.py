import logging
import sys
from contextlib import contextmanager
from types import MethodType
from typing import TYPE_CHECKING

from grouper.oneoff import BaseOneOff
from grouper.plugin.load import load_plugins

if TYPE_CHECKING:
    from argparse import Namespace
    from grouper.ctl.settings import CtlSettings
    from grouper.models.session import Session
    from grouper.repositories.factory import SessionFactory
    from typing import Any, Iterator, Tuple


@contextmanager
def wrapped_session(session, make_read_only):
    # type: (Session, bool) -> Iterator[Session]
    """Simple wrapper around a sqlalchemy session allowing it to be used in a
    context and to be made read-only.

    Args:
        session(sqlalchemy.orm.session.Session): the session to wrapped
        make_read_only(bool): whether to monkey patch the session to be read-only
    """
    real_session_flush = session.flush
    real_session_is_clean = session._is_clean

    if make_read_only:
        # HACK: monkey patch sqlachemy session so nothing writes to
        # database but things think that it did
        def is_clean_ro(self):
            # type: (Session) -> bool
            return True

        def flush_ro(self, objects=None):
            # type: (Session, Any) -> None
            pass

        session.flush = MethodType(flush_ro, session)
        session._is_clean = MethodType(is_clean_ro, session)

        yield session

        session.flush = real_session_flush
        session._is_clean = real_session_is_clean

        # remove any changes
        session.rollback()
    else:
        yield session


def key_value_arg_type(arg):
    # type: (str) -> Tuple[str, str]
    """Simple validate/transform function to use in argparse as a 'type' for an
    argument where the argument is of the form 'key=value'."""
    k, v = arg.split("=", 1)
    return (k, v)


def oneoff_command(args, settings, session_factory):
    # type: (Namespace, CtlSettings, SessionFactory) -> None
    session = session_factory.create_session()

    oneoffs = load_plugins(
        BaseOneOff, settings.oneoff_dirs, settings.oneoff_module_paths, "grouper-ctl"
    )

    if args.subcommand == "run":
        logging.info("running one-off with '{}'".format(sys.argv))

        if args.dry_run:
            logging.warning("running in DRY RUN mode")
        else:
            logging.warning("NOT running in dry run mode")

        with wrapped_session(session, make_read_only=args.dry_run) as the_session:
            for oneoff in oneoffs:
                if oneoff.__class__.__name__ == args.classname:
                    params = args.oneoff_arguments or []
                    params += [("dry_run", args.dry_run)]
                    oneoff.run(the_session, **dict(params))

    elif args.subcommand == "list":
        for oneoff in oneoffs:
            logging.info(oneoff.__class__.__name__)


def add_parser(subparsers):
    oneoff_parser = subparsers.add_parser("oneoff", help="run/list one off external scripts")
    oneoff_parser.set_defaults(func=oneoff_command)
    oneoff_subparser = oneoff_parser.add_subparsers(dest="subcommand")

    oneoff_subparser.add_parser("list", help="list available one-offs")

    oneoff_run_parser = oneoff_subparser.add_parser("run", help="run specific one-off")
    oneoff_run_parser.add_argument("classname", help="class name of the one-off to run")
    oneoff_run_parser.add_argument(
        "oneoff_arguments",
        type=key_value_arg_type,
        nargs="*",
        help="arguments to pass to one-off, 'key=value' pairs",
    )

    dry_run_parser = oneoff_run_parser.add_mutually_exclusive_group(required=False)
    dry_run_parser.add_argument("--dry_run", dest="dry_run", action="store_true")
    dry_run_parser.add_argument("--no-dry_run", dest="dry_run", action="store_false")
    dry_run_parser.set_defaults(dry_run=True)
