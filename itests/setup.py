"""Utilities to set up integration tests.

Contains only test setup code specific to integration tests, such as spawning separate servers and
managing Selenium.  More general test setup code goes in tests.setup.
"""

import errno
import logging
import socket
import subprocess
import time
from contextlib import closing, contextmanager
from typing import TYPE_CHECKING

from selenium.webdriver import Chrome, ChromeOptions

from tests.path_util import bin_env, db_url, src_path

if TYPE_CHECKING:
    from py.local import LocalPath
    from typing import Iterator


def _get_unused_port():
    # type: () -> int
    """Bind, requesting a system-allocated port, and return it.

    This isn't strictly correct in that there's a race condition where the port could be taken by
    something else before the server we launch uses it.  Hopefully this will not be common.
    """
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_until_accept(port, timeout=3.0):
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
def frontend_server(tmpdir, user):
    # type: (LocalPath, str) -> Iterator[str]
    proxy_port = _get_unused_port()
    fe_port = _get_unused_port()

    cmds = [
        [
            src_path("bin", "grouper-ctl"),
            "-vvc",
            src_path("config", "dev.yaml"),
            "user_proxy",
            "-P",
            str(fe_port),
            "-p",
            str(proxy_port),
            user,
        ],
        [
            src_path("bin", "grouper-fe"),
            "-vvc",
            src_path("config", "dev.yaml"),
            "-p",
            str(fe_port),
            "-d",
            db_url(tmpdir),
        ],
    ]

    subprocesses = []
    for cmd in cmds:
        logging.info("Starting command: %s", " ".join(cmd))
        p = subprocess.Popen(cmd, env=bin_env())
        subprocesses.append(p)

    logging.info("Waiting on server to come online")
    _wait_until_accept(proxy_port)
    _wait_until_accept(fe_port)
    logging.info("Connection established")

    yield "http://localhost:{}".format(proxy_port)

    for p in subprocesses:
        p.kill()


def selenium_browser():
    # type: () -> Chrome
    options = ChromeOptions()
    options.add_argument("headless")
    options.add_argument("no-sandbox")
    options.add_argument("window-size=1920,1080")
    return Chrome(chrome_options=options)
