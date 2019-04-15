import argparse
import logging
import sys
from typing import TYPE_CHECKING

from grouper import __version__
from grouper.background.background_processor import BackgroundProcessor
from grouper.background.settings import BackgroundSettings
from grouper.error_reporting import get_sentry_client, setup_signal_handlers
from grouper.models.base.session import get_db_engine, Session
from grouper.plugin import initialize_plugins
from grouper.plugin.exceptions import PluginsDirectoryDoesNotExist
from grouper.settings import default_settings_path
from grouper.setup import setup_logging
from grouper.util import get_database_url

if TYPE_CHECKING:
    from argparse import Namespace
    from grouper.error_reporting import SentryProxy
    from typing import List


def build_arg_parser():
    description_msg = "Grouper Background"
    parser = argparse.ArgumentParser(description=description_msg)

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
        version="%%(prog)s %s" % __version__,
        help="Display version information.",
    )
    return parser


def start_processor(args, settings, sentry_client):
    # type: (Namespace, BackgroundSettings, SentryProxy) -> None
    log_level = logging.getLevelName(logging.getLogger().level)
    logging.info("begin. log_level={}".format(log_level))

    try:
        initialize_plugins(
            settings.plugin_dirs, settings.plugin_module_paths, "grouper-background"
        )
    except PluginsDirectoryDoesNotExist as e:
        logging.fatal("Plugin directory does not exist: {}".format(e))
        sys.exit(1)

    # setup database
    logging.debug("configure database session")
    Session.configure(bind=get_db_engine(get_database_url(settings)))

    background = BackgroundProcessor(settings, sentry_client)
    background.run()


def main(sys_argv=sys.argv):
    # type: (List[str]) -> None
    setup_signal_handlers()

    # get arguments
    parser = build_arg_parser()
    args = parser.parse_args(sys_argv[1:])

    try:
        # load settings
        settings = BackgroundSettings.global_settings_from_config(args.config)

        # setup logging
        setup_logging(args, settings.log_format)

        # setup sentry
        sentry_client = get_sentry_client(settings.sentry_dsn)
    except Exception:
        logging.exception("uncaught exception in startup")
        sys.exit(1)

    start_processor(args, settings, sentry_client)
