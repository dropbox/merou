"""Utilities to set up integration tests.

Contains only test setup code specific to integration tests, such as spawning separate servers and
managing Selenium.  More general test setup code goes in tests.setup.
"""

import errno
import logging
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from typing import TYPE_CHECKING

from selenium.webdriver import Chrome, ChromeOptions

from tests.path_util import bin_env, db_url, src_path

if TYPE_CHECKING:
    from py.local import LocalPath
    from typing import Iterator


def _bind_socket():
    # type: () -> socket.socket
    """Bind a system-allocated port and return it."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    return s


def _wait_until_accept(port, timeout=5.0):
    # type: (int, float) -> None
    """Wait until a server accepts connections on the specified port."""
    deadline = time.time() + timeout
    while True:
        socket_timeout = deadline - time.time()
        if socket_timeout < 0.0:
            assert False, "server did not start on port {} within {}s".format(port, timeout)
        try:
            s = socket.socket()
            s.settimeout(socket_timeout)
            s.connect(("localhost", port))
        except socket.timeout:
            pass
        except socket.error as e:
            if e.errno not in [errno.ETIMEDOUT, errno.ECONNREFUSED]:
                raise
        else:
            s.close()
            return
        time.sleep(0.1)


@contextmanager
def api_server(tmpdir):
    # type: (LocalPath) -> Iterator[str]
    api_socket = _bind_socket()
    api_port = api_socket.getsockname()[1]

    cmd = [
        sys.executable,
        src_path("bin", "grouper-api"),
        "-vvc",
        src_path("config", "test.yaml"),
        "-d",
        db_url(tmpdir),
        "--listen-stdin",
    ]

    logging.info("Starting server with command: %s", " ".join(cmd))
    p = subprocess.Popen(cmd, env=bin_env(), stdin=api_socket.fileno())
    api_socket.close()

    logging.info("Waiting on server to come online")
    _wait_until_accept(api_port)
    logging.info("Connection established")

    yield "localhost:{}".format(api_port)

    p.terminate()


@contextmanager
def frontend_server(tmpdir, user):
    # type: (LocalPath, str) -> Iterator[str]
    proxy_socket = _bind_socket()
    proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    proxy_port = proxy_socket.getsockname()[1]
    fe_socket = _bind_socket()
    fe_port = fe_socket.getsockname()[1]

    proxy_cmd = [
        sys.executable,
        src_path("bin", "grouper-ctl"),
        "-vvc",
        src_path("config", "test.yaml"),
        "user_proxy",
        "-P",
        str(fe_port),
        "-p",
        str(proxy_port),
        user,
    ]
    fe_cmd = [
        sys.executable,
        src_path("bin", "grouper-fe"),
        "-vvc",
        src_path("config", "test.yaml"),
        "-d",
        db_url(tmpdir),
        "--listen-stdin",
    ]

    subprocesses = []

    logging.info("Starting command: %s", " ".join(fe_cmd))
    fe_process = subprocess.Popen(fe_cmd, env=bin_env(), stdin=fe_socket.fileno())
    subprocesses.append(fe_process)
    fe_socket.close()

    # TODO(rra): There is a race condition here because grouper-ctl user_proxy doesn't implement
    # --listen-stdin yet, which in turn is because the built-in Python HTTPServer doesn't support
    # wrapping a pre-existing socket.  Since we have to close the socket so that grouper-ctl
    # user_proxy can re-open it, something else might grab it in the interim.  Once it is rewritten
    # using Tornado, it can use the same approach as the frontend and API servers and take an open
    # socket on standard input.  At that point, we can also drop the SO_REUSEADDR above, which is
    # there to protect against the race condition.
    logging.info("Starting command: %s", " ".join(proxy_cmd))
    proxy_socket.close()
    proxy_process = subprocess.Popen(proxy_cmd, env=bin_env())
    subprocesses.append(proxy_process)

    logging.info("Waiting on server to come online")
    _wait_until_accept(fe_port)
    _wait_until_accept(proxy_port)
    logging.info("Connection established")

    yield "http://localhost:{}".format(proxy_port)

    for p in subprocesses:
        p.terminate()


def selenium_browser():
    # type: () -> Chrome
    options = ChromeOptions()
    if os.environ.get("HEADLESS", "true") != "false":
        options.add_argument("headless")
    options.add_argument("no-sandbox")
    options.add_argument("window-size=1920,1080")
    return Chrome(options=options)
