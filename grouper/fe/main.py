from __future__ import print_function

import logging
import os
import sys
from contextlib import closing
from typing import TYPE_CHECKING

import tornado.httpserver
import tornado.ioloop

import grouper.fe
from grouper import stats
from grouper.app import GrouperApplication
from grouper.database import DbRefreshThread
from grouper.error_reporting import get_sentry_client, setup_signal_handlers
from grouper.fe.routes import HANDLERS
from grouper.fe.settings import FrontendSettings
from grouper.fe.template_util import get_template_env
from grouper.graph import Graph
from grouper.models.base.session import get_db_engine, Session
from grouper.plugin import get_plugin_proxy, initialize_plugins
from grouper.plugin.exceptions import PluginsDirectoryDoesNotExist
from grouper.setup import build_arg_parser, setup_logging
from grouper.util import get_database_url

if TYPE_CHECKING:
    from argparse import Namespace
    from grouper.error_reporting import SentryProxy
    from typing import Callable, List


def create_fe_application(
    settings,  # type: FrontendSettings
    deployment_name,  # type: str
    xsrf_cookies=True,  # type: bool
    session=None,  # type: Callable[[], Session]
):
    # type: (...) -> GrouperApplication
    tornado_settings = {
        "debug": settings.debug,
        "static_path": os.path.join(os.path.dirname(grouper.fe.__file__), "static"),
        "xsrf_cookies": xsrf_cookies,
    }
    extra_globals = {"cdnjs_prefix": settings.cdnjs_prefix}
    handler_settings = {
        "session": session if session else Session,
        "template_env": get_template_env(
            deployment_name=deployment_name, extra_globals=extra_globals
        ),
    }
    handlers = [(route, handler_class, handler_settings) for (route, handler_class) in HANDLERS]
    return GrouperApplication(handlers, **tornado_settings)


def start_server(args, settings, sentry_client):
    # type: (Namespace, FrontendSettings, SentryProxy) -> None
    log_level = logging.getLevelName(logging.getLogger().level)
    logging.info("begin. log_level={}".format(log_level))

    assert not (
        settings.debug and settings.num_processes > 1
    ), "debug mode does not support multiple processes"

    try:
        initialize_plugins(settings.plugin_dirs, settings.plugin_module_paths, "grouper_fe")
    except PluginsDirectoryDoesNotExist as e:
        logging.fatal("Plugin directory does not exist: {}".format(e))
        sys.exit(1)

    # setup database
    logging.debug("configure database session")
    database_url = args.database_url or get_database_url(settings)
    Session.configure(bind=get_db_engine(database_url))

    application = create_fe_application(settings, args.deployment_name)

    address = args.address or settings.address
    port = args.port or settings.port

    ssl_context = get_plugin_proxy().get_ssl_context()

    logging.info(
        "Starting application server with %d processes on port %d", settings.num_processes, port
    )
    server = tornado.httpserver.HTTPServer(application, ssl_options=ssl_context)
    server.bind(port, address=address)
    # When using multiple processes, the forking happens here
    server.start(settings.num_processes)

    stats.set_defaults()

    # Create the Graph and start the graph update thread post fork to ensure each process gets
    # updated.
    with closing(Session()) as session:
        graph = Graph()
        graph.update_from_db(session)

    refresher = DbRefreshThread(settings, graph, settings.refresh_interval, sentry_client)
    refresher.daemon = True
    refresher.start()

    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        tornado.ioloop.IOLoop.instance().stop()
    finally:
        print("Bye")


def main(sys_argv=sys.argv):
    # type: (List[str]) -> None
    setup_signal_handlers()

    # get arguments
    parser = build_arg_parser("Grouper Web Server.")
    args = parser.parse_args(sys_argv[1:])

    try:
        # load settings
        settings = FrontendSettings.global_settings_from_config(args.config)

        # setup logging
        setup_logging(args, settings.log_format)

        # setup sentry
        sentry_client = get_sentry_client(settings.sentry_dsn)
    except Exception:
        logging.exception("uncaught exception in startup")
        sys.exit(1)

    try:
        start_server(args, settings, sentry_client)
    except Exception:
        sentry_client.captureException()
    finally:
        logging.info("end")
