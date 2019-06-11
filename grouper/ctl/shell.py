import code
from pprint import pprint
from typing import TYPE_CHECKING

from grouper.graph import GroupGraph

if TYPE_CHECKING:
    from argparse import Namespace
    from grouper.ctl.settings import CtlSettings
    from grouper.repositories.factory import SessionFactory


def shell_command(args, settings, session_factory):
    # type: (Namespace, CtlSettings, SessionFactory) -> None
    session = session_factory.create_session()
    graph = GroupGraph.from_db(session)
    pp = pprint

    try:
        from IPython import embed
    except ImportError:
        code.interact(local={"session": session, "graph": graph, "pp": pp})
    else:
        embed()


def add_parser(subparsers):
    shell_parser = subparsers.add_parser("shell", help="Launch a shell.")
    shell_parser.set_defaults(func=shell_command)
