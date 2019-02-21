import argparse
import logging
import sys
from typing import TYPE_CHECKING

from grouper import __version__
from grouper.ctl import dump_sql, group, oneoff, service_account, shell, sync_db, user, user_proxy
from grouper.ctl.factory import CtlCommandFactory
from grouper.plugin import initialize_plugins
from grouper.plugin.exceptions import PluginsDirectoryDoesNotExist
from grouper.settings import default_settings_path, settings
from grouper.util import get_loglevel

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.models.base.session import Session
    from typing import List, Optional

sa_log = logging.getLogger("sqlalchemy.engine.base.Engine")


def main(sys_argv=sys.argv, start_config_thread=True, session=None, graph=None):
    # type: (List[str], bool, Optional[Session], Optional[GroupGraph]) -> None
    description_msg = "Grouper Control"
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

    command_factory = CtlCommandFactory(session, graph)

    subparsers = parser.add_subparsers(dest="command")
    command_factory.add_all_parsers(subparsers)

    # Add parsers for legacy commands that have not been refactored.
    for subcommand_module in [
        dump_sql,
        group,
        oneoff,
        service_account,
        shell,
        sync_db,
        user,
        user_proxy,
    ]:
        subcommand_module.add_parser(subparsers)  # type: ignore

    args = parser.parse_args(sys_argv[1:])

    if start_config_thread:
        settings.update_from_config(args.config)
        settings.start_config_thread(args.config)

    log_level = get_loglevel(args, base=logging.INFO)
    logging.basicConfig(level=log_level, format=settings.log_format)

    try:
        initialize_plugins(settings.plugin_dirs, settings.plugin_module_paths, "grouper-ctl")
    except PluginsDirectoryDoesNotExist as e:
        logging.fatal("Plugin directory does not exist: {}".format(e))
        sys.exit(1)

    if log_level < 0:
        sa_log.setLevel(logging.INFO)

    # Old-style subcommands store a func in callable when setting up their arguments.  New-style
    # subcommands are handled via a factory that constructs and calls the correct object.
    if getattr(args, "func", None):
        args.func(args)
    else:
        command = command_factory.construct_command(args.command)
        command.run(args)
