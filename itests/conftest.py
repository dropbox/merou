"""Provide pytest fixtures for test setup.

When testing with a persistent database, we have to explicitly close the database session after
each test.  Otherwise, the presence of an open session will prevent dropping all tables to ensure a
clean test context.  The easiest way to provide that is via pytest fixtures.

This file is automatically loaded by pytest and injects available fixtures into every test without
requiring the flake8 noqa annotations normally needed by explicit fixture imports.
"""

from contextlib import closing
from typing import TYPE_CHECKING

import pytest

from itests.setup import selenium_browser
from tests.setup import SetupTest

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from typing import Iterator


@pytest.fixture(scope="session")
def browser():
    # type: () -> Iterator[Chrome]
    driver = selenium_browser()
    yield driver
    driver.quit()


@pytest.fixture
def setup(tmpdir):
    # type: (LocalPath) -> Iterator[SetupTest]
    with closing(SetupTest(tmpdir)) as test_setup:
        yield test_setup
