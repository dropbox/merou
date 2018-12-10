import BaseHTTPServer
import getpass
import logging
import urllib2

from mrproxy import UserProxyHandler


# Workaround for https://github.com/gmjosack/mrproxy/issues/2
class ProxyHandler(UserProxyHandler):
    def do_request(self, request):
        try:
            url = urllib2.urlopen(request)
            code = url.getcode()
            headers = str(url.info())
            data = url.read()
        except urllib2.HTTPError as err:
            code = err.getcode()
            headers = str(err.info())
            data = err.read()
        except urllib2.URLError as err:
            code = 503
            headers = str(err)
            data = "503 Service Unavailable: %s\n" % err

        self.send_response(code)
        self.wfile.write(headers)
        self.end_headers()
        self.wfile.write(data)


def build_user_proxy_server(username, backend_port, listen_host, listen_port):
    class ServerArgs(object):
        def __init__(self, backend_port, username):
            self.backend_port = backend_port
            self.header = ["X-Grouper-User: %s" % username]

    server = BaseHTTPServer.HTTPServer(
        (listen_host, listen_port), ProxyHandler
    )
    server.args = ServerArgs(backend_port, username)

    return server


def user_proxy_command(args):
    username = args.username
    if username is None:
        username = getpass.getuser()
        logging.debug("No username provided, using (%s)", username)

    server = build_user_proxy_server(
        args.username,
        args.backend_port,
        args.listen_host,
        args.listen_port
    )
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
