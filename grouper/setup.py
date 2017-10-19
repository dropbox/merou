from argparse import ArgumentParser, Namespace  # noqa
import logging


from grouper import __version__
from grouper.settings import default_settings_path


def build_arg_parser(description):
    # type(str) -> ArgumentParser

    parser = ArgumentParser(description=description)

    parser.add_argument(
            "-c", "--config", default=default_settings_path(), help="Path to config file.")
    parser.add_argument(
            "-v", "--verbose", action="count", default=0, help="Increase logging verbosity.")
    parser.add_argument(
            "-q", "--quiet", action="count", default=0, help="Decrease logging verbosity.")
    parser.add_argument(
            "-V", "--version", action="version", version="%%(prog)s {}".format(__version__),
            help="Display version information.")
    parser.add_argument(
            "-a", "--address", type=str, default=None, help="Override address in config.")
    parser.add_argument(
            "-p", "--port", type=int, default=None, help="Override port in config.")
    parser.add_argument(
            "-n", "--deployment-name", type=str, default="", help="Name of the deployment.")

    return parser


def setup_logging(args, log_format):
    # type: (Namespace, str) -> None

    # `logging` levels are integer multiples of 10. so each verbose/quiet level
    # is multiplied by 10
    verbose = args.verbose * 10
    quiet = args.quiet * 10
    log_level = logging.getLogger().level - verbose + quiet

    sa_log = logging.getLogger("sqlalchemy.engine.base.Engine")

    logging.basicConfig(level=log_level, format=log_format)
    if log_level < 0:
        sa_log.setLevel(logging.INFO)
