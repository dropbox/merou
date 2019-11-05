import sys
from typing import TYPE_CHECKING

from tornado.httpserver import HTTPRequest

from grouper.plugin.base import BasePlugin
from grouper.plugin.proxy import PluginProxy

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Optional, Type


class RandomException(Exception):
    pass


class ExceptionLoggerTestPlugin(BasePlugin):
    def __init__(self):
        # type: () -> None
        self.request = None  # type: Optional[HTTPRequest]
        self.status = None  # type: Optional[int]
        self.exc_type = None  # type: Optional[Type[BaseException]]
        self.exc_value = None  # type: Optional[BaseException]
        self.exc_tb = None  # type: Optional[TracebackType]

    def log_exception(
        self,
        request,  # type: Optional[HTTPRequest]
        status,  # type: Optional[int]
        exc_type,  # type: Optional[Type[BaseException]]
        exc_value,  # type: Optional[BaseException]
        exc_tb,  # type: Optional[TracebackType]
    ):
        # type: (...) -> None
        self.request = request
        self.status = status
        self.exc_type = exc_type
        self.exc_value = exc_value
        self.exc_tb = exc_tb


def test_exception_plugin():
    # type: () -> None
    test_logger = ExceptionLoggerTestPlugin()
    proxy = PluginProxy([test_logger])

    try:
        raise RandomException("some string")
    except RandomException:
        proxy.log_exception(None, None, *sys.exc_info())

    assert test_logger.request is None
    assert test_logger.status is None
    assert test_logger.exc_type == RandomException
    assert str(test_logger.exc_value) == "some string"
    assert test_logger.exc_tb is not None

    # Reinitializing test_logger unconfuses mypy, which otherwise thinks that test_logger.request
    # must still be None.  See mypy/issues/4168.
    test_logger = ExceptionLoggerTestPlugin()
    proxy = PluginProxy([test_logger])

    try:
        raise RandomException("with request")
    except RandomException:
        request = HTTPRequest("GET", "/foo")
        proxy.log_exception(request, 200, *sys.exc_info())

    assert test_logger.request is not None
    assert test_logger.request.uri == "/foo"
    assert test_logger.status == 200
    assert test_logger.exc_type == RandomException
    assert str(test_logger.exc_value) == "with request"
    assert test_logger.exc_tb is not None
