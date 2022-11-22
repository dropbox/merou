import logging
from argparse import ArgumentParser
from typing import TYPE_CHECKING

from grouper import __version__
from grouper.log_redact import RedactingFormatter
from grouper.settings import default_settings_path
from grouper.util import get_loglevel

if TYPE_CHECKING:
    from argparse import Namespace


def build_arg_parser(description):
    # type: (str) -> ArgumentParser

    parser = ArgumentParser(description=description)

    parser.add_argument(
        "-c", "--config", default=default_settings_path(), help="Path to config file."
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase logging verbosity."
    )
    parser.add_argument(
        "-q", "--quiet", action="count", default=0, help="Decrease logging verbosity."
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="%%(prog)s {}".format(__version__),
        help="Display version information.",
    )
    parser.add_argument(
        "-a", "--address", type=str, default=None, help="Override address in config."
    )
    parser.add_argument("-p", "--port", type=int, default=None, help="Override port in config.")
    parser.add_argument(
        "-n", "--deployment-name", type=str, default="", help="Name of the deployment."
    )
    parser.add_argument(
        "-d", "--database-url", type=str, default=None, help="Override database URL in config."
    )
    parser.add_argument(
        "--listen-stdin",
        action="store_true",
        help="Ignore address and port and expect connections on standard input",
    )

    return parser


def setup_logging(args, log_format):
    # type: (Namespace, str) -> None
    log_level = get_loglevel(args)

    sa_log = logging.getLogger("sqlalchemy.engine.base.Engine")

    logging.basicConfig(level=log_level, format=log_format)
    if log_level < 0:
        sa_log.setLevel(logging.INFO)

    for handler in logging.root.handlers:
        handler.setFormatter(RedactingFormatter(log_format))
