from argparse import ArgumentParser, Namespace  # noqa
import logging
import os.path


from grouper import __version__


def parse_args(parser, default_config_path):
    # type(ArgumentParser, str) -> Namespace
    parser.add_argument(
            "-c", "--config", default=default_config_path, help="Path to config file.")
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

    return parser.parse_args()


def setup_logging(args, log_format):
    # type: (Namespace, str) -> None

    verbose = args.verbose * 10
    quiet = args.quiet * 10
    log_level = logging.getLogger().level - verbose + quiet

    sa_log = logging.getLogger("sqlalchemy.engine.base.Engine")

    logging.basicConfig(level=log_level, format=log_format)
    if log_level < 0:
        sa_log.setLevel(logging.INFO)


def load_plugins(settings, service_name):
    if settings.plugin_dir:
        assert os.path.exists(settings.plugin_dir), "Plugin directory does not exist"
        load_plugins(settings.plugin_dir, service_name=service_name)
