from __future__ import print_function

import logging
import os
import socket
import sys
from contextlib import closing
from typing import TYPE_CHECKING

from tornado.curl_httpclient import CurlAsyncHTTPClient
from tornado.httpclient import AsyncHTTPClient
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop

import grouper.fe
from grouper.app import GrouperApplication
from grouper.database import DbRefreshThread
from grouper.error_reporting import setup_signal_handlers
from grouper.fe.routes import HANDLERS
from grouper.fe.settings import FrontendSettings
from grouper.fe.templating import FrontendTemplateEngine
from grouper.graph import Graph
from grouper.models.base.session import get_db_engine, Session
from grouper.plugin import set_global_plugin_proxy
from grouper.plugin.exceptions import PluginsDirectoryDoesNotExist
from grouper.plugin.proxy import PluginProxy
from grouper.setup import build_arg_parser, setup_logging

if TYPE_CHECKING:
    from argparse import Namespace
    from typing import Callable, List


def create_fe_application(
    settings,  # type: FrontendSettings
    deployment_name,  # type: str
    xsrf_cookies=True,  # type: bool
    session=None,  # type: Callable[[], Session]
):
    # type: (...) -> GrouperApplication
    static_path = os.path.join(os.path.dirname(grouper.fe.__file__), "static")
    tornado_settings = {
        "debug": settings.debug,
        "session": session if session else Session,
        "static_path": static_path,
        "template_engine": FrontendTemplateEngine(settings, deployment_name, static_path),
        "xsrf_cookies": xsrf_cookies,
    }
    return GrouperApplication(HANDLERS, **tornado_settings)


def start_server(args, settings, plugins):
    # type: (Namespace, FrontendSettings, PluginProxy) -> None
    log_level = logging.getLevelName(logging.getLogger().level)
    logging.info("begin. log_level={}".format(log_level))

    assert not (
        settings.debug and settings.num_processes > 1
    ), "debug mode does not support multiple processes"

    # setup database
    logging.debug("configure database session")
    if args.database_url:
        settings.database = args.database_url
    Session.configure(bind=get_db_engine(settings.database))

    application = create_fe_application(settings, args.deployment_name)
    ssl_context = plugins.get_ssl_context()

    if args.listen_stdin:
        logging.info(
            "Starting application server with %d processes on stdin", settings.num_processes
        )
        server = HTTPServer(application, ssl_options=ssl_context)
        s = socket.socket(fileno=sys.stdin.fileno())
        s.setblocking(False)
        s.listen()
        server.add_sockets([s])
    else:
        address = args.address or settings.address
        port = args.port or settings.port
        logging.info(
            "Starting application server with %d processes on %s:%d",
            settings.num_processes,
            address,
            port,
        )
        server = HTTPServer(application, ssl_options=ssl_context)
        server.bind(port, address=address)

    # When using multiple processes, the forking happens here
    server.start(settings.num_processes)

    # Create the Graph and start the graph update thread post fork to ensure each process gets
    # updated.
    with closing(Session()) as session:
        graph = Graph()
        graph.update_from_db(session)

    refresher = DbRefreshThread(settings, plugins, graph, settings.refresh_interval)
    refresher.daemon = True
    refresher.start()

    try:
        IOLoop.current().start()
    except KeyboardInterrupt:
        IOLoop.current().stop()
    finally:
        print("Bye")


def main(sys_argv=sys.argv):
    # type: (List[str]) -> None
    setup_signal_handlers()

    # The curl HTTP client is required to support proxies.
    AsyncHTTPClient.configure(CurlAsyncHTTPClient)

    # get arguments
    parser = build_arg_parser("Grouper Web Server.")
    args = parser.parse_args(sys_argv[1:])

    try:
        settings = FrontendSettings.global_settings_from_config(args.config)
        setup_logging(args, settings.log_format)
        plugins = PluginProxy.load_plugins(settings, "grouper-fe")
        set_global_plugin_proxy(plugins)
    except PluginsDirectoryDoesNotExist as e:
        logging.fatal("Plugin directory does not exist: {}".format(e))
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
