import errno
import socket
import subprocess
import time

from groupy.client import Groupy
import pytest
import selenium

from tests.path_util import db_url, src_path


def _get_unused_port():
    return _get_unused_ports(1)[0]


def _get_unused_ports(count):
    sockets = []
    ports = []
    try:
        for _ in range(count):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sockets.append(s)
            s.bind(('0.0.0.0', 0))
            ports.append(s.getsockname()[1])
            s.close()
    finally:
        for s in sockets:
            s.close()

    if len(ports) != count:
        raise Exception("Could not allocate all ports")

    return ports


@pytest.yield_fixture
def async_server(standard_graph, tmpdir):
    ports = _get_unused_ports(2)

    proxy_port = ports[0]
    fe_port = ports[1]

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
            "cbguder@a.co"
        ],
        [
            src_path("bin", "grouper-fe"),
            "-c",
            src_path("config", "dev.yaml"),
            "-p",
            str(fe_port),
            "-d",
            db_url(tmpdir),
        ]
    ]

    subprocesses = []

    for cmd in cmds:
        print("Starting command: " + " ".join(cmd))
        p = subprocess.Popen(cmd)
        subprocesses.append(p)

    print("Waiting on server to come online")
    wait_until_accept(proxy_port)

    print("Connection established")
    yield "http://localhost:{}".format(proxy_port)

    for p in subprocesses:
        p.kill()


@pytest.yield_fixture
def async_api_server(standard_graph, tmpdir):
    api_port = _get_unused_port()

    cmd = [
        src_path("bin", "grouper-api"),
        "-c",
        src_path("config", "dev.yaml"),
        "-p",
        str(api_port),
        "-d",
        db_url(tmpdir),
    ]

    print("Starting server with command: " + " ".join(cmd))
    p = subprocess.Popen(cmd)

    print("Waiting on server to come online")
    wait_until_accept(api_port)

    print("Connection established")
    yield "localhost:{}".format(api_port)

    p.kill()


@pytest.yield_fixture
def browser():
    options = selenium.webdriver.ChromeOptions()
    options.add_argument("headless")
    options.add_argument("no-sandbox")
    options.add_argument("window-size=1920,1080")

    driver = selenium.webdriver.Chrome(chrome_options=options)

    yield driver

    driver.quit()


@pytest.fixture
def api_client(async_api_server):
    return Groupy(async_api_server)


def wait_until_accept(port, timeout=10.0):
    deadline = time.time() + timeout

    while True:
        try:
            socket_timeout = deadline - time.time()
            if socket_timeout < 0.0:
                raise Exception("Deadline exceeded")

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
