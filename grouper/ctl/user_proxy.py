from __future__ import print_function

import getpass
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import cast, TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPErrorProcessor, Request

from grouper.ctl.base import CtlCommand

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace
    from grouper.ctl.settings import CtlSettings
    from urllib.request import _HTTPResponse, _UrlopenRet
    from typing import Dict, Tuple, Type


class NoRedirectHandler(HTTPErrorProcessor):
    """Redirect handler that returns the redirect to the client.

    We don't want the proxy to follow redirects itself since the client's concept of the current
    URL will then desynchronize from the page that was retured.  We want to be transparent and
    return each intermediate response.
    """

    def http_response(self, request, response):
        # type: (Request, _HTTPResponse) -> _UrlopenRet
        return response


class ProxyServer(HTTPServer):
    """Very simple proxy that adds the X-Grouper-User header.

    This is not intended for production use and should not be exposed to hostile requests.  It's
    based on the implementation in mrproxy.
    """

    def __init__(self, settings, address, handler_class, backend_port, username):
        # type: (CtlSettings, Tuple[str, int], Type[BaseHTTPRequestHandler], int, str) -> None
        self.backend_port = backend_port
        self.user_auth_header = settings.user_auth_header
        self.username = username
        self.opener = build_opener(NoRedirectHandler)
        super().__init__(address, handler_class)


class ProxyHandler(BaseHTTPRequestHandler):
    """Handler for the proxy server."""

    @property
    def dest_url(self):
        # type: () -> str
        backend_port = cast(ProxyServer, self.server).backend_port
        return "http://localhost:{}{}".format(backend_port, self.path)

    def do_request(self, request):
        # type: (Request) -> None
        try:
            url = cast(ProxyServer, self.server).opener.open(request)
            assert url, "urlopen for {} returned None".format(self.dest_url)
            code = url.getcode()
            msg = getattr(url, "msg", "")
            headers = str(url.info()).rstrip()
            data = url.read()
        except HTTPError as e:
            code = e.getcode()
            msg = getattr(url, "msg", "")
            headers = str(e.info()).rstrip()
            data = e.read()
        except (AssertionError, URLError) as e:
            code = 503
            msg = "Service Unavailable"
            headers = ""
            data = "503 Service Unavailable: {}\n".format(str(e)).encode()

        self.send_response(code, msg)
        for line in headers.splitlines():
            header, value = line.split(": ", 1)
            self.send_header(header, value)
        self.end_headers()
        self.wfile.write(data)

    def updated_headers(self):
        # type: () -> Dict[str, str]
        headers = {h: str(v) for h, v in self.headers.items()}
        user_auth_header = cast(ProxyServer, self.server).user_auth_header
        headers[user_auth_header] = cast(ProxyServer, self.server).username
        return headers

    def do_GET(self):
        # type: () -> None
        headers = self.updated_headers()
        request = Request(self.dest_url, headers=headers)
        self.do_request(request)

    def do_POST(self):
        # type: () -> None
        content_len = int(str(self.headers["Content-Length"]))
        data = self.rfile.read(content_len)
        headers = self.updated_headers()
        request = Request(self.dest_url, headers=headers, data=data)
        self.do_request(request)


class UserProxyCommand(CtlCommand):
    """Command to start a user proxy."""

    @staticmethod
    def add_arguments(parser):
        # type: (ArgumentParser) -> None
        parser.add_argument("--listen-host", default="localhost", help="Host to listen on.")
        parser.add_argument(
            "-p", "--listen-port", default=8888, type=int, help="Port to listen on."
        )
        parser.add_argument(
            "-P", "--backend-port", default=8989, type=int, help="Port to proxy to."
        )
        parser.add_argument("username", nargs="?", default=None)

    def __init__(self, settings):
        # type: (CtlSettings) -> None
        self.settings = settings

    def run(self, args):
        # type: (Namespace) -> None
        username = args.username
        if username is None:
            username = getpass.getuser()
            logging.debug("No username provided, using (%s)", username)

        server = ProxyServer(
            settings=self.settings,
            address=(args.listen_host, args.listen_port),
            handler_class=ProxyHandler,
            backend_port=args.backend_port,
            username=args.username,
        )

        logging.info(
            "Starting user_proxy on %s:%d with user %s",
            args.listen_host,
            args.listen_port,
            username,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Bye!")
