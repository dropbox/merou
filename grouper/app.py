"""Code common to all Grouper UIs using Tornado.

Provides GrouperApplication, a subclass of Tornado's Application class, with standardized logging.
"""

from typing import TYPE_CHECKING

from tornado.log import access_log
from tornado.web import Application

if TYPE_CHECKING:
    from tornado.web import RequestHandler


class GrouperApplication(Application):
    def log_request(self, handler):
        # type: (RequestHandler) -> None
        if handler.get_status() < 400:
            log_method = access_log.info
        elif handler.get_status() < 500:
            log_method = access_log.warning
        else:
            log_method = access_log.error

        # we want to reduce priority of health check request
        if handler.request.uri == "/debug/stats":
            log_method = access_log.debug

        if handler.current_user:
            username = handler.current_user.username
        else:
            username = "-"

        request_time = 1000.0 * handler.request.request_time()

        # This is a private method of Tornado and thus isn't in typeshed for Python 2.
        #
        # TODO(rra): Replace this with a custom log_function setting that prepents the username.
        summary = handler._request_summary()  # type: ignore[attr-defined]

        log_method(
            "{} {} {} {:.2f}ms".format(username, handler.get_status(), summary, request_time)
        )
