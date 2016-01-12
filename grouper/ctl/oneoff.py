from contextlib import contextmanager
import logging
import sys
import types

from annex import Annex

from grouper.ctl.util import make_session
from grouper.models import load_plugins
from grouper.oneoff import BaseOneOff
from grouper.settings import settings


@contextmanager
def wrapped_session(session, make_read_only):
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
            return True

        def flush_ro(self, objects=None):
            pass

        session.flush = types.MethodType(flush_ro, session)
        session._is_clean = types.MethodType(is_clean_ro, session)

        yield session

        session.flush = real_session_flush
        session._is_clean = real_session_is_clean

        # remove any changes
        session.rollback()
    else:
        yield session


def key_value_arg_type(arg):
    """Simple validate/transform function to use in argparse as a 'type' for an
    argument where the argument is of the form 'key=value'."""
    print 'arg={}'.format(arg)
    k, v = arg.split('=', 1)
    return (k, v)


def oneoff_command(args):
    session = make_session()
    load_plugins(settings["plugin_dir"], service_name="grouper-ctl")

    oneoffs = Annex(BaseOneOff, [settings["oneoff_dir"]], raise_exceptions=True)
    for oneoff in oneoffs:
        oneoff.configure(service_name="grouper-ctl")

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
                    params += [('dry_run', args.dry_run)]
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
    oneoff_run_parser.add_argument("oneoff_arguments", type=key_value_arg_type, nargs="*",
            help="arguments to pass to one-off, 'key=value' pairs")

    dry_run_parser = oneoff_run_parser.add_mutually_exclusive_group(required=False)
    dry_run_parser.add_argument("--dry_run", dest="dry_run", action="store_true")
    dry_run_parser.add_argument("--no-dry_run", dest="dry_run", action="store_false")
    dry_run_parser.set_defaults(dry_run=True)
