import argparse
import logging
import sys
from typing import TYPE_CHECKING

from grouper import __version__
from grouper.ctl import group, oneoff, shell
from grouper.ctl.factory import CtlCommandFactory
from grouper.ctl.settings import CtlSettings
from grouper.initialization import create_sql_usecase_factory
from grouper.plugin import set_global_plugin_proxy
from grouper.plugin.exceptions import PluginsDirectoryDoesNotExist
from grouper.plugin.proxy import PluginProxy
from grouper.repositories.factory import SessionFactory, SingletonSessionFactory
from grouper.settings import default_settings_path
from grouper.setup import setup_logging

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import List, Optional


def main(sys_argv=sys.argv, session=None):
    # type: (List[str], Optional[Session]) -> None
    description_msg = "Grouper Control"
    parser = argparse.ArgumentParser(description=description_msg)

    parser.add_argument(
        "-c", "--config", default=default_settings_path(), help="Path to config file."
    )
    parser.add_argument(
        "-d", "--database-url", type=str, default=None, help="Override database URL in config."
    )
    parser.add_argument(
        "-q", "--quiet", action="count", default=0, help="Decrease logging verbosity."
    )
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase logging verbosity."
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="%%(prog)s %s" % __version__,
        help="Display version information.",
    )

    subparsers = parser.add_subparsers(dest="command")
    CtlCommandFactory.add_all_parsers(subparsers)

    # Add parsers for legacy commands that have not been refactored.
    for subcommand_module in [group, oneoff, shell]:
        subcommand_module.add_parser(subparsers)  # type: ignore[attr-defined]

    args = parser.parse_args(sys_argv[1:])

    # Construct the CtlSettings object used for all commands, and set it as the global Settings
    # object.  All code in grouper.ctl.* takes the CtlSettings object as an argument if needed, but
    # it may call other legacy code that requires the global Settings object be present.
    settings = CtlSettings.global_settings_from_config(args.config)
    if args.database_url:
        settings.database = args.database_url

    setup_logging(args, settings.log_format)

    # Construct a session factory, which is passed into all the legacy commands that haven't been
    # converted to usecases yet.
    if session:
        session_factory = SingletonSessionFactory(session)  # type: SessionFactory
    else:
        session_factory = SessionFactory(settings)

    # Initialize plugins.  The global plugin proxy is used by legacy code.
    try:
        plugins = PluginProxy.load_plugins(settings, "grouper-ctl")
    except PluginsDirectoryDoesNotExist as e:
        logging.fatal("Plugin directory does not exist: {}".format(e))
        sys.exit(1)
    set_global_plugin_proxy(plugins)

    # Set up factories.
    usecase_factory = create_sql_usecase_factory(settings, plugins, session_factory)
    command_factory = CtlCommandFactory(settings, usecase_factory)

    # Old-style subcommands store a func in callable when setting up their arguments.  New-style
    # subcommands are handled via a factory that constructs and calls the correct object.
    if getattr(args, "func", None):
        args.func(args, settings, session_factory)
    else:
        command = command_factory.construct_command(args.command)
        command.run(args)
