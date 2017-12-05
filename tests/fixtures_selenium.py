import subprocess

import pytest
import yaml

from fixtures import standard_graph  # noqa: F401
from path_util import db_url, src_path


selenium = pytest.importorskip("selenium")


def _write_test_config(tmpdir):
    with open(src_path("config", "dev.yaml")) as config_file:
        config = yaml.safe_load(config_file.read())

    config["common"]["database"] = db_url(tmpdir)

    config_path = str(tmpdir.join("grouper.yaml"))
    with open(config_path, "w") as config_file:
        yaml.safe_dump(config, config_file)

    return config_path


@pytest.yield_fixture
def async_server(standard_graph, tmpdir):
    config_path = _write_test_config(tmpdir)

    cmds = [
        [
            src_path("bin", "grouper-ctl"),
            "-vvc",
            config_path,
            "user_proxy",
            "cbguder@a.co"
        ],
        [
            src_path("bin", "grouper-fe"),
            "-c",
            config_path
        ]
    ]

    subprocesses = []

    for cmd in cmds:
        p = subprocess.Popen(cmd)
        subprocesses.append(p)

    yield "http://localhost:8888"

    for p in subprocesses:
        p.kill()


@pytest.yield_fixture
def browser():
    options = selenium.webdriver.ChromeOptions()
    options.add_argument("headless")
    options.add_argument("window-size=1920,1080")

    try:
        driver = selenium.webdriver.Chrome(chrome_options=options)
    except selenium.common.exceptions.WebDriverException:
        pytest.skip("could not initialize Selenium Chrome webdriver")

    yield driver

    driver.quit()
