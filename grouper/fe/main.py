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
from grouper.app import Application
from grouper.database import DbRefreshThread
from grouper.error_reporting import get_sentry_client, setup_signal_handlers
from grouper.fe.routes import HANDLERS
from grouper.fe.settings import settings
from grouper.fe.template_util import get_template_env
from grouper.graph import Graph
from grouper.models.base.session import get_db_engine, Session
from grouper.plugin import get_plugin_proxy, initialize_plugins
from grouper.plugin.exceptions import PluginsDirectoryDoesNotExist
from grouper.setup import build_arg_parser, setup_logging
from grouper.util import get_database_url

if TYPE_CHECKING:
    import argparse
    from typing import List
    from grouper.error_reporting import SentryProxy
    from grouper.fe.settings import Settings


def get_application(settings, sentry_client, deployment_name):
    # type: (Settings, SentryProxy, str) -> Application
    tornado_settings = {
        "static_path": os.path.join(os.path.dirname(grouper.fe.__file__), "static"),
        "debug": settings.debug,
        "xsrf_cookies": True,
    }

    my_settings = {
        "db_session": Session,
        "template_env": get_template_env(deployment_name=deployment_name),
    }

    application = Application(
        HANDLERS, my_settings=my_settings, sentry_client=sentry_client, **tornado_settings
    )

    return application


def start_server(args, sentry_client):
    # type: (argparse.Namespace, SentryProxy) -> None

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

    application = get_application(settings, sentry_client, args.deployment_name)

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

    # Create the Graph and start the config / graph update threads post fork to ensure each
    # process gets updated.

    settings.start_config_thread(args.config, "fe")

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
        settings.update_from_config(args.config, "fe")

        # setup logging
        setup_logging(args, settings.log_format)

        # setup sentry
        sentry_client = get_sentry_client(settings.sentry_dsn)
    except Exception:
        logging.exception("uncaught exception in startup")
        sys.exit(1)

    try:
        start_server(args, sentry_client)
    except Exception:
        sentry_client.captureException()
    finally:
        logging.info("end")
