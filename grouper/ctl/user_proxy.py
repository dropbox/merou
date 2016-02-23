import BaseHTTPServer
import getpass
import logging

from mrproxy import UserProxyHandler


def user_proxy_command(args):
    class ServerArgs(object):
        def __init__(self, backend_port, username):
            self.backend_port = backend_port
            self.header = ["X-Grouper-User: %s" % username]

    username = args.username
    if username is None:
        username = getpass.getuser()
        logging.debug("No username provided, using (%s)", username)

    server = BaseHTTPServer.HTTPServer(
        (args.listen_host, args.listen_port), UserProxyHandler
    )
    server.args = ServerArgs(args.backend_port, args.username)
    try:
        logging.info(
            "Starting user_proxy on host (%s) and port (%s) with user (%s)",
            args.listen_host, args.listen_port, username
        )
        server.serve_forever()
    except KeyboardInterrupt:
        print "Bye!"


def add_parser(subparsers):
    user_proxy_parser = subparsers.add_parser("user_proxy",
                                              help="Start a development reverse proxy.")
    user_proxy_parser.set_defaults(func=user_proxy_command)
    user_proxy_parser.add_argument("--listen-host", default="localhost",
                                   help="Host to listen on.")
    user_proxy_parser.add_argument("-p", "--listen-port", default=8888, type=int,
                                   help="Port to listen on.")
    user_proxy_parser.add_argument("-P", "--backend-port", default=8989, type=int,
                                   help="Port to proxy to.")
    user_proxy_parser.add_argument("username", nargs="?", default=None)
