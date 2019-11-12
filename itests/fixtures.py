"""Tiny fixture wrapper around the new functions in itests.setup.

We want to move away from using fixtures and instead start the server we're testing using a context
manager, but not all of the tests have been converted.  This is a thin wrapper around the new
functions to provide them as fixtures for older tests until the refactoring is complete.
"""

from typing import TYPE_CHECKING

import pytest

from itests.setup import frontend_server

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from py.local import LocalPath
    from typing import Iterator


@pytest.fixture
def async_server(standard_graph, tmpdir):
    # type: (GroupGraph, LocalPath) -> Iterator[str]
    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        yield frontend_url
