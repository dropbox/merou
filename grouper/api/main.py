from __future__ import print_function

import logging
import sys
from contextlib import closing
from typing import TYPE_CHECKING

import tornado.httpserver
import tornado.ioloop

from grouper import stats
from grouper.api.routes import HANDLERS
from grouper.api.settings import ApiSettings
from grouper.app import GrouperApplication
from grouper.database import DbRefreshThread
from grouper.error_reporting import get_sentry_client, setup_signal_handlers
from grouper.graph import Graph
from grouper.initialization import create_graph_usecase_factory
from grouper.models.base.session import get_db_engine, Session
from grouper.plugin import initialize_plugins
from grouper.plugin.exceptions import PluginsDirectoryDoesNotExist
from grouper.setup import build_arg_parser, setup_logging

if TYPE_CHECKING:
    from argparse import Namespace
    from grouper.error_reporting import SentryProxy
    from grouper.graph import GroupGraph
    from grouper.usecases.factory import UseCaseFactory
    from typing import List


def create_api_application(graph, settings, usecase_factory):
    # type: (GroupGraph, ApiSettings, UseCaseFactory) -> GrouperApplication
    tornado_settings = {"debug": settings.debug}
    handler_settings = {"graph": graph, "usecase_factory": usecase_factory}
    handlers = [(route, handler_class, handler_settings) for (route, handler_class) in HANDLERS]
    return GrouperApplication(handlers, **tornado_settings)


def start_server(args, settings, sentry_client):
    # type: (Namespace, ApiSettings, SentryProxy) -> None
    log_level = logging.getLevelName(logging.getLogger().level)
    logging.info("begin. log_level={}".format(log_level))

    assert not (
        settings.debug and settings.num_processes > 1
    ), "debug mode does not support multiple processes"

    try:
        initialize_plugins(settings.plugin_dirs, settings.plugin_module_paths, "grouper_api")
    except PluginsDirectoryDoesNotExist as e:
        logging.fatal("Plugin directory does not exist: {}".format(e))
        sys.exit(1)

    # setup database
    logging.debug("configure database session")
    if args.database_url:
        settings.database = args.database_url
    Session.configure(bind=get_db_engine(settings.database_url))

    with closing(Session()) as session:
        graph = Graph()
        graph.update_from_db(session)

    refresher = DbRefreshThread(settings, graph, settings.refresh_interval, sentry_client)
    refresher.daemon = True
    refresher.start()

    usecase_factory = create_graph_usecase_factory(settings, graph=graph)
    application = create_api_application(graph, settings, usecase_factory)

    address = args.address or settings.address
    port = args.port or settings.port

    logging.info("Starting application server on port %d", port)
    server = tornado.httpserver.HTTPServer(application)
    server.bind(port, address=address)
    server.start(settings.num_processes)

    stats.set_defaults()

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
    parser = build_arg_parser("Grouper API Server.")
    args = parser.parse_args(sys_argv[1:])

    try:
        # load settings
        settings = ApiSettings.global_settings_from_config(args.config)

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
