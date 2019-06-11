"""Tiny fixture wrapper around the new functions in itests.setup.

We want to move away from using fixtures and instead start the server we're testing using a context
manager, but not all of the tests have been converted.  This is a thin wrapper around the new
functions to provide them as fixtures for older tests until the refactoring is complete.
"""

from typing import TYPE_CHECKING

import pytest
from groupy.client import Groupy

from itests.setup import api_server, frontend_server

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from py.local import LocalPath
    from typing import Iterator


@pytest.fixture
def async_server(standard_graph, tmpdir):
    # type: (GroupGraph, LocalPath) -> Iterator[str]
    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        yield frontend_url


@pytest.fixture
def async_api_server(standard_graph, tmpdir):
    with api_server(tmpdir) as api_url:
        yield api_url


@pytest.fixture
def api_client(async_api_server):
    return Groupy(async_api_server)
