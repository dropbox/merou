from datetime import datetime
from functools import wraps
import logging
import re
import sys
from typing import TypeVar
import urllib
import urlparse
from uuid import uuid4

from expvar.stats import stats
from plop.collector import Collector
import sqlalchemy.exc
import tornado.web
from tornado.web import RequestHandler

from grouper import perf_profile
from grouper.constants import AUDIT_SECURITY, RESERVED_NAMES, USERNAME_VALIDATION
from grouper.fe.settings import settings
from grouper.graph import Graph
from grouper.models.base.session import get_db_engine, Session
from grouper.models.user import User
from grouper.user_permissions import user_permissions
from grouper.util import get_database_url


class Alert(object):
    def __init__(self, severity, message, heading=None):
        self.severity = severity
        self.message = message
        if heading is None:
            self.heading = severity.title() + "!"
        else:
            self.heading = heading


class DatabaseFailure(Exception):
    pass


class InvalidUser(Exception):
    pass


T = TypeVar('T')  # noqa


# if raven library around, pull in SentryMixin
try:
    from raven.contrib.tornado import SentryMixin
except ImportError:
    pass
else:
    class SentryHandler(SentryMixin, RequestHandler):
        pass
    RequestHandler = SentryHandler  # type: ignore # no support for conditional declarations #1152


class GrouperHandler(RequestHandler):
    def initialize(self):
        self.session = self.application.my_settings.get("db_session")()
        self.graph = Graph()

        if self.get_argument("_profile", False):
            self.perf_collector = Collector()
            self.perf_trace_uuid = str(uuid4())
            self.perf_collector.start()
        else:
            self.perf_collector = None
            self.perf_trace_uuid = None

        self._request_start_time = datetime.utcnow()
        stats.incr("requests")
        stats.incr("requests_{}".format(self.__class__.__name__))

    def write_error(self, status_code, **kwargs):
        """Override for custom error page."""
        if status_code >= 500 and status_code < 600:
            template = self.application.my_settings["template_env"].get_template("errors/5xx.html")
            self.write(template.render({"is_active": self.is_active}))
        else:
            template = self.application.my_settings["template_env"].get_template(
                    "errors/generic.html")
            self.write(template.render({
                    "status_code": status_code,
                    "message": self._reason,
                    "is_active": self.is_active,
                    "trace_uuid": self.perf_trace_uuid,
                    }))
        self.finish()

    def is_refresh(self):
        # type: () -> bool
        """Indicates whether the refresh argument for this handler has been
        set to yes. This is used to force a refresh of the cached graph so
        that we don't show inconsistent state to the user.

        Returns:
            a boolean indicating whether this handler should refresh the graph
        """
        return self.get_argument("refresh", "no").lower() == "yes"

    # The refresh argument can be added to any page.  If the handler for that
    # route calls this function, it will sync its graph from the database if
    # requested.
    def handle_refresh(self):
        if self.is_refresh():
            self.graph.update_from_db(self.session)

    def redirect(self, url, *args, **kwargs):
        if self.is_refresh():
            url = urlparse.urljoin(url, "?refresh=yes")
        return super(GrouperHandler, self).redirect(url, *args, **kwargs)

    def get_current_user(self):
        username = self.request.headers.get(settings.user_auth_header)
        if not username:
            return

        # Users must be fully qualified
        if not re.match("^{}$".format(USERNAME_VALIDATION), username):
            raise InvalidUser()

        try:
            user, created = User.get_or_create(self.session, username=username)
            if created:
                logging.info("Created new user %s", username)
                self.session.commit()
                # Because the graph doesn't initialize until the updates table
                # is populated, we need to refresh the graph here in case this
                # is the first update.
                self.graph.update_from_db(self.session)
        except sqlalchemy.exc.OperationalError:
            # Failed to connect to database or create user, try to reconfigure the db. This invokes
            # the fetcher to try to see if our URL string has changed.
            Session.configure(bind=get_db_engine(get_database_url(settings)))
            raise DatabaseFailure()

        return user

    def prepare(self):
        if not self.current_user or not self.current_user.enabled:
            self.forbidden()
            self.finish()
            return

    def on_finish(self):
        if self.perf_collector:
            self.perf_collector.stop()
            perf_profile.record_trace(self.session, self.perf_collector, self.perf_trace_uuid)

        self.session.close()

        # log request duration
        duration = datetime.utcnow() - self._request_start_time
        duration_ms = int(duration.total_seconds() * 1000)
        stats.incr("duration_ms", duration_ms)
        stats.incr("duration_ms_{}".format(self.__class__.__name__), duration_ms)

        # log response status code
        response_status = self.get_status()
        stats.incr("response_status_{}".format(response_status))
        stats.incr("response_status_{}_{}".format(self.__class__.__name__, response_status))

    def update_qs(self, **kwargs):
        qs = self.request.arguments.copy()
        qs.update(kwargs)
        return "?" + urllib.urlencode(qs, True)

    def is_active(self, test_path):
        path = self.request.path
        if path == test_path:
            return "active"
        return ""

    def get_template_namespace(self):
        namespace = super(GrouperHandler, self).get_template_namespace()
        namespace.update({
            "update_qs": self.update_qs,
            "is_active": self.is_active,
            "perf_trace_uuid": self.perf_trace_uuid,
            "xsrf_form": self.xsrf_form_html,
            "alerts": [],
        })
        return namespace

    def render_template(self, template_name, **kwargs):
        template = self.application.my_settings["template_env"].get_template(template_name)
        content = template.render(kwargs)
        return content

    def render(self, template_name, **kwargs):
        context = {}
        context.update(self.get_template_namespace())
        context.update(kwargs)
        self.write(self.render_template(template_name, **context))

    def get_form_alerts(self, errors):
        alerts = []
        for field, field_errors in errors.items():
            for error in field_errors:
                alerts.append(Alert("danger", error, field))
        return alerts

    def raise_and_log_exception(self, exc):
        try:
            raise exc
        except Exception:
            self.log_exception(*sys.exc_info())

    def log_message(self, message, **kwargs):
        if self.captureMessage:
            self.captureMessage(message, **kwargs)
        else:
            logging.info("{}, kwargs={}".format(message, kwargs))

    # TODO(gary): Add json error responses.
    def badrequest(self, format_type=None):
        self.set_status(400)
        self.raise_and_log_exception(tornado.web.HTTPError(400))
        self.render("errors/badrequest.html")

    def forbidden(self, format_type=None):
        self.set_status(403)
        self.raise_and_log_exception(tornado.web.HTTPError(403))
        self.render("errors/forbidden.html")

    def notfound(self, format_type=None):
        self.set_status(404)
        self.raise_and_log_exception(tornado.web.HTTPError(404))
        self.render("errors/notfound.html")

    def get_sentry_user_info(self):
        user = self.get_current_user()
        return {
                'username': user.name,
                }


def test_reserved_names(permission_name):
    """Returns a list of strings explaining which reserved regexes match a
    proposed permission name.
    """
    failure_messages = []
    for reserved in RESERVED_NAMES:
        if re.match(reserved, permission_name):
            failure_messages.append(
                "Permission names must not match the pattern: %s" % (reserved, )
            )
    return failure_messages


def ensure_audit_security(perm_arg):
    """Decorator for web handler methods to ensure the current_user has the
    AUDIT_SECURITY permission with the specified argument.

    Args:
        perm_arg: the argument required for the audit permission. only 'public_keys' at this point.
    """
    def _wrapper(f):
        def _decorator(self, *args, **kwargs):
            if not any([name == AUDIT_SECURITY and argument == perm_arg for name, argument, _, _
                    in user_permissions(self.session, self.current_user)]):
                return self.forbidden()

            return f(self, *args, **kwargs)

        return wraps(f)(_decorator)

    return _wrapper


def paginate_results(handler, results):
    # type: (GrouperHandler, List[T]) -> tuple[int, int, int, List[T]]
    """Limits the number of results to display for handlers/templates the paginate lists

    Args:
        handler: the GrouperHandler for the request being paginated
        results: the entire list of possible results

    Returns:
        the total number of results, the offset, the limit, and the limited results to show
            for this page
    """
    total = len(results)
    offset = int(handler.get_argument("offset", 0))
    limit = int(handler.get_argument("limit", 100))
    if limit > 9000:
        limit = 9000

    return total, offset, limit, results[offset:offset + limit]


def form_http_verbs(function):
    """This decorator is used to support forms submitted using POST as if they were
    submitted using less common HTTP verbs, such as delete. After annotating the
    post function in the handler, all forms that have the appropriate field
    (HTTP_VERB) will have their requests routed through the appropriate function
    instead of the annotated function. This allows us to use these HTTP verbs
    where possible, and then fall back to using forms via POST while still using
    the same code path. See the http_verb macro in macros/ui.html for implementing
    the form field.
    """
    def inner(self, *args, **kwargs):
        if "HTTP_VERB" in self.request.arguments:
            func = getattr(self, self.request.arguments["HTTP_VERB"][0].lower())
            return func(*args, **kwargs)
        return function(self, *args, **kwargs)
    return inner
