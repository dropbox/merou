import logging

from annex import Annex

from grouper.ctl.util import make_session
from grouper.models import load_plugins
from grouper.oneoff import BaseOneOff
from grouper.settings import settings


def oneoff_command(args):
    session = make_session()
    models.load_plugins(settings["plugin_dir"], service_name="grouper-ctl")

    oneoffs = Annex(BaseOneOff, [settings["oneoff_dir"]], raise_exceptions=True)
    for oneoff in oneoffs:
        oneoff.configure(service_name="grouper-ctl")

    if args.subcommand == "run":
        for oneoff in oneoffs:
            if oneoff.__class__.__name__ == args.classname:
                params = args.oneoff_arguments or []
                oneoff.run(session, *params)
    elif args.subcommand == "list":
        for oneoff in oneoffs:
            logging.info(oneoff.__class__.__name__)

def add_parser(subparsers):
    oneoff_parser = subparsers.add_parser("oneoff", help="run/list one off external scripts")
    oneoff_parser.set_defaults(func=oneoff_command)
    oneoff_subparser = oneoff_parser.add_subparsers(dest="subcommand")

    oneoff_list_parser = oneoff_subparser.add_parser("list", help="list available one-offs")

    oneoff_run_parser = oneoff_subparser.add_parser("run", help="run specific one-off")
    oneoff_run_parser.add_argument("classname", help="class name of the one-off to run")
    oneoff_run_parser.add_argument("oneoff_arguments", nargs="*",
            help="arguments to pass to one-off")
