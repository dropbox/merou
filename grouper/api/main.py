from __future__ import print_function

import logging
import socket
import sys
from contextlib import closing
from typing import TYPE_CHECKING

from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop

from grouper.api.routes import HANDLERS
from grouper.api.settings import ApiSettings
from grouper.app import GrouperApplication
from grouper.database import DbRefreshThread
from grouper.error_reporting import setup_signal_handlers
from grouper.graph import Graph
from grouper.initialization import create_graph_usecase_factory
from grouper.models.base.session import get_db_engine, Session
from grouper.plugin import set_global_plugin_proxy
from grouper.plugin.exceptions import PluginsDirectoryDoesNotExist
from grouper.plugin.proxy import PluginProxy
from grouper.setup import build_arg_parser, setup_logging

if TYPE_CHECKING:
    from argparse import Namespace
    from grouper.graph import GroupGraph
    from grouper.usecases.factory import UseCaseFactory
    from typing import List


def create_api_application(graph, settings, plugins, usecase_factory):
    # type: (GroupGraph, ApiSettings, PluginProxy, UseCaseFactory) -> GrouperApplication
    tornado_settings = {"debug": settings.debug}
    handler_settings = {"graph": graph, "plugins": plugins, "usecase_factory": usecase_factory}
    handlers = [(route, handler_class, handler_settings) for (route, handler_class) in HANDLERS]
    return GrouperApplication(handlers, **tornado_settings)


def start_server(args, settings, plugins):
    # type: (Namespace, ApiSettings, PluginProxy) -> None
    log_level = logging.getLevelName(logging.getLogger().level)
    logging.info("begin. log_level=%s", log_level)

    assert not (
        settings.debug and settings.num_processes > 1
    ), "debug mode does not support multiple processes"

    # setup database
    logging.debug("configure database session")
    if args.database_url:
        settings.database = args.database_url
    Session.configure(bind=get_db_engine(settings.database))

    with closing(Session()) as session:
        graph = Graph()
        graph.update_from_db(session)

    refresher = DbRefreshThread(settings, plugins, graph, settings.refresh_interval)
    refresher.daemon = True
    refresher.start()

    usecase_factory = create_graph_usecase_factory(settings, plugins, graph=graph)
    application = create_api_application(graph, settings, plugins, usecase_factory)

    if args.listen_stdin:
        logging.info("Starting application server on stdin")
        server = HTTPServer(application)
        s = socket.socket(fileno=sys.stdin.fileno())
        s.setblocking(False)
        s.listen()
        server.add_sockets([s])
    else:
        address = args.address or settings.address
        port = args.port or settings.port
        logging.info("Starting application server on %s:%d", address, port)
        server = HTTPServer(application)
        server.bind(port, address=address)

    server.start(settings.num_processes)

    try:
        IOLoop.current().start()
    except KeyboardInterrupt:
        IOLoop.current().stop()
    finally:
        print("Bye")


def main(sys_argv=sys.argv):
    # type: (List[str]) -> None
    setup_signal_handlers()

    # get arguments
    parser = build_arg_parser("Grouper API Server")
    args = parser.parse_args(sys_argv[1:])

    try:
        settings = ApiSettings.global_settings_from_config(args.config)
        setup_logging(args, settings.log_format)
        plugins = PluginProxy.load_plugins(settings, "grouper-api")
        set_global_plugin_proxy(plugins)
    except PluginsDirectoryDoesNotExist as e:
        logging.fatal("Plugin directory does not exist: %s", e)
        sys.exit(1)
    except Exception:
        logging.exception("Uncaught exception in startup")
        sys.exit(1)

    try:
        start_server(args, settings, plugins)
    except Exception:
        plugins.log_exception(None, None, *sys.exc_info())
        logging.exception("Uncaught exception")
    finally:
        logging.info("end")
