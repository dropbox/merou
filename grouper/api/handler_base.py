from datetime import datetime
import sys

from expvar.stats import stats
from tornado.web import HTTPError, RequestHandler

from grouper.perf_profile import get_stopwatch as sw, stopwatch_emit_stats

# if raven library around, pull in SentryMixin
try:
    from raven.contrib.tornado import SentryMixin
except ImportError:
    pass
else:
    class SentryHandler(SentryMixin, RequestHandler):
        pass
    RequestHandler = SentryHandler  # type: ignore # no support for conditional declarations #1152


class GraphHandler(RequestHandler):
    def initialize(self):
        self.graph = self.application.my_settings.get("graph")
        self.session = self.application.my_settings.get("db_session")()

        self._request_start_time = datetime.utcnow()
        stats.incr("requests")
        stats.incr("requests_{}".format(self.__class__.__name__))

        sw().start('sw-{}'.format(self.__class__.__name__))

    def on_finish(self):
        # log request duration
        duration = datetime.utcnow() - self._request_start_time
        duration_ms = int(duration.total_seconds() * 1000)
        stats.incr("duration_ms", duration_ms)
        stats.incr("duration_ms_{}".format(self.__class__.__name__), duration_ms)

        # log response status code
        response_status = self.get_status()
        stats.incr("response_status_{}".format(response_status))
        stats.incr("response_status_{}_{}".format(self.__class__.__name__, response_status))

        # log stopwatch metrics
        sw().end('sw-{}'.format(self.__class__.__name__))
        stopwatch_emit_stats()

    def error(self, errors):
        errors = [
            {"code": code, "message": message} for code, message in errors
        ]
        with self.graph.lock:
            checkpoint = self.graph.checkpoint
            checkpoint_time = self.graph.checkpoint_time
            self.write({
                "status": "error",
                "errors": errors,
                "checkpoint": checkpoint,
                "checkpoint_time": checkpoint_time,
            })

    def success(self, data):
        with self.graph.lock:
            checkpoint = self.graph.checkpoint
            checkpoint_time = self.graph.checkpoint_time
            self.write({
                "status": "ok",
                "data": data,
                "checkpoint": checkpoint,
                "checkpoint_time": checkpoint_time,
            })

    def raise_and_log_exception(self, exc):
        try:
            raise exc
        except Exception:
            self.log_exception(*sys.exc_info())

    def notfound(self, message):
        self.set_status(404)
        self.raise_and_log_exception(HTTPError(404))
        self.error([(404, message)])

    def write_error(self, status_code, **kwargs):
        """Overrides tornado's uncaught exception handler to return JSON results."""
        if "exc_info" in kwargs:
            typ, value, _ = kwargs["exc_info"]
            self.error([(status_code, traceback.format_exception_only(typ, value))])
        else:
            self.error([(status_code, None)])
