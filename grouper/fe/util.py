import json
import logging
import re
import sys
from datetime import datetime
from functools import wraps
from typing import TYPE_CHECKING
from uuid import uuid4

import sqlalchemy.exc
import tornado.web
from plop.collector import Collector
from six import iteritems
from six.moves.urllib.parse import quote, unquote, urlencode, urljoin
from tornado.web import HTTPError, RequestHandler

from grouper.constants import AUDIT_SECURITY, RESERVED_NAMES, USERNAME_VALIDATION
from grouper.fe.settings import settings
from grouper.graph import Graph
from grouper.initialization import create_graph_usecase_factory
from grouper.models.base.session import get_db_engine, Session
from grouper.models.user import User
from grouper.perf_profile import record_trace
from grouper.plugin import get_plugin_proxy
from grouper.repositories.factory import SingletonSessionFactory
from grouper.user_permissions import user_permissions

if TYPE_CHECKING:
    from grouper.fe.templating import FrontendTemplateEngine
    from types import TracebackType
    from typing import Any, Callable, Dict, List, Optional, Text, Type


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


class GrouperHandler(RequestHandler):
    def initialize(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        self.graph = Graph()
        self.session = self.settings["session"]()  # type: Session
        self.template_engine = self.settings["template_engine"]  # type: FrontendTemplateEngine
        self.plugins = get_plugin_proxy()
        session_factory = SingletonSessionFactory(self.session)
        self.usecase_factory = create_graph_usecase_factory(
            settings(), self.plugins, session_factory
        )

        if self.get_argument("_profile", False):
            self.perf_collector = Collector()
            self.perf_trace_uuid = str(uuid4())  # type: Optional[str]
            self.perf_collector.start()
        else:
            self.perf_collector = None
            self.perf_trace_uuid = None

        self._request_start_time = datetime.utcnow()

    def set_default_headers(self):
        # type: () -> None
        self.set_header("Content-Security-Policy", self.settings["template_engine"].csp_header())
        self.set_header("Referrer-Policy", "same-origin")

    def log_exception(
        self,
        exc_type,  # type: Optional[Type[BaseException]]
        exc_value,  # type: Optional[BaseException]
        exc_tb,  # type: Optional[TracebackType]
    ):
        # type: (...) -> None
        if isinstance(exc_value, HTTPError):
            status_code = exc_value.status_code
        else:
            status_code = 500
        self.plugins.log_exception(self.request, status_code, exc_type, exc_value, exc_tb)
        super(GrouperHandler, self).log_exception(exc_type, exc_value, exc_tb)

    def write_error(self, status_code, **kwargs):
        # type: (int, **Any) -> None
        """Override for custom error page."""
        message = kwargs.get("message", "Unknown error")
        if status_code >= 500 and status_code < 600:
            template = self.template_engine.get_template("errors/5xx.html")
            self.write(
                template.render({"is_active": self.is_active, "static_url": self.static_url})
            )
        else:
            template = self.template_engine.get_template("errors/generic.html")
            self.write(
                template.render(
                    {
                        "status_code": status_code,
                        "message": message,
                        "is_active": self.is_active,
                        "trace_uuid": self.perf_trace_uuid,
                        "static_url": self.static_url,
                    }
                )
            )
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
        # type: () -> None
        if self.is_refresh():
            self.graph.update_from_db(self.session)

    def redirect(self, url, *args, **kwargs):
        # type: (str, *Any, **Any) -> None
        if self.is_refresh():
            url = urljoin(url, "?refresh=yes")
        alerts = kwargs.pop("alerts", [])  # type: List[Alert]
        self.set_alerts(alerts)
        super(GrouperHandler, self).redirect(url, *args, **kwargs)

    def get_or_create_user(self, username):
        # type: (str) -> Optional[User]
        """Retrieve or create the User object for the authenticated user.

        This is done in a separate method called by prepare instead of in the magic Tornado
        get_current_user method because exceptions thrown by the latter are caught by Tornado and
        not propagated to the caller, and we want to use exceptions to handle invalid users and
        then return an error page in prepare.
        """
        if not username:
            return None

        # Users must be fully qualified
        if not re.match("^{}$".format(USERNAME_VALIDATION), username):
            raise InvalidUser("{} does not match {}".format(username, USERNAME_VALIDATION))

        # User must exist in the database and be active
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
            Session.configure(bind=get_db_engine(settings().database))
            raise DatabaseFailure()

        # service accounts are, by definition, not interactive users
        if user.is_service_account:
            raise InvalidUser("{} is a service account".format(username))

        return user

    def prepare(self):
        # type: () -> None
        username = self.request.headers.get(settings().user_auth_header)

        try:
            user = self.get_or_create_user(username)
        except InvalidUser as e:
            self.baduser(str(e))
            self.finish()
            return

        if user and user.enabled:
            self.current_user = user
        else:
            self.baduser("{} is not an active account".format(username))
            self.finish()

    def on_finish(self):
        # type: () -> None
        if self.perf_collector:
            self.perf_collector.stop()
            record_trace(self.session, self.perf_collector, self.perf_trace_uuid)

        self.session.close()

        handler = self.__class__.__name__
        duration_ms = int((datetime.utcnow() - self._request_start_time).total_seconds() * 1000)
        response_status = self.get_status()
        self.plugins.log_request(handler, response_status, duration_ms)

    def update_qs(self, **kwargs):
        # type: (**Any) -> str
        qs = self.request.arguments.copy()
        qs.update(kwargs)
        return "?" + urlencode(sorted(qs.items()), True)

    def is_active(self, test_path):
        # type: (str) -> str
        path = self.request.path
        if path == test_path:
            return "active"
        return ""

    def get_template_namespace(self):
        # type: () -> Dict[str, Any]
        namespace = super(GrouperHandler, self).get_template_namespace()
        namespace.update(
            {
                "update_qs": self.update_qs,
                "is_active": self.is_active,
                "perf_trace_uuid": self.perf_trace_uuid,
                "xsrf_form": self.xsrf_form_html,
                "alerts": self.get_alerts(),
                "static_url": self.static_url,
            }
        )
        return namespace

    def render_template(self, template_name, **kwargs):
        # type: (str, **Any) -> Text
        template = self.template_engine.get_template(template_name)
        content = template.render(kwargs)
        return content

    def render(self, template_name, **kwargs):
        # type: (str, **Any) -> None
        defaults = self.get_template_namespace()

        context = {}
        context.update(defaults)
        context.update(kwargs)

        # Merge alerts
        context["alerts"] = []
        context["alerts"].extend(defaults.get("alerts", []))
        context["alerts"].extend(kwargs.get("alerts", []))

        self.write(self.render_template(template_name, **context))

    def set_alerts(self, alerts):
        # type: (List[Alert]) -> None
        if len(alerts) > 0:
            self.set_cookie("_alerts", _serialize_alerts(alerts))
        else:
            self.clear_cookie("_alerts")

    def get_alerts(self):
        # type: () -> List[Alert]
        serialized_alerts = self.get_cookie("_alerts", default="[]")
        alerts = _deserialize_alerts(serialized_alerts)
        self.clear_cookie("_alerts")
        return alerts

    def get_form_alerts(self, errors):
        # type: (Dict[str, List[str]]) -> List[Alert]
        alerts = []
        for field, field_errors in iteritems(errors):
            for error in field_errors:
                alerts.append(Alert("danger", error, field))
        return alerts

    def raise_and_log_exception(self, exc):
        # type: (Exception) -> None
        try:
            raise exc
        except Exception:
            self.log_exception(*sys.exc_info())

    def log_message(self, message, **kwargs):
        # type: (str, **Any) -> None
        logging.info("{}, kwargs={}".format(message, kwargs))

    def badrequest(self):
        # type: () -> None
        self.set_status(400)
        self.raise_and_log_exception(tornado.web.HTTPError(400))
        self.render("errors/badrequest.html")

    def baduser(self, message):
        # type: (str) -> None
        self.set_status(403)
        self.raise_and_log_exception(tornado.web.HTTPError(403))
        how_to_get_help = settings().how_to_get_help
        self.render("errors/baduser.html", message=message, how_to_get_help=how_to_get_help)

    def forbidden(self):
        # type: () -> None
        self.set_status(403)
        self.raise_and_log_exception(tornado.web.HTTPError(403))
        self.render("errors/forbidden.html", how_to_get_help=settings().how_to_get_help)

    def notfound(self):
        # type: () -> None
        self.set_status(404)
        self.raise_and_log_exception(tornado.web.HTTPError(404))
        self.render("errors/notfound.html")


def test_reserved_names(permission_name):
    # type: (str) -> List[str]
    """Returns a list of strings explaining which reserved regexes match a
    proposed permission name.
    """
    failure_messages = []
    for reserved in RESERVED_NAMES:
        if re.match(reserved, permission_name):
            failure_messages.append(
                "Permission names must not match the pattern: %s" % (reserved,)
            )
    return failure_messages


def ensure_audit_security(perm_arg):
    # type: (Text) -> Callable[[Callable[..., None]], Callable[..., None]]
    """Decorator for web handler methods to ensure the current_user has the
    AUDIT_SECURITY permission with the specified argument.

    Args:
        perm_arg: the argument required for the audit permission. only 'public_keys' at this point.
    """

    def _wrapper(f):
        # type: (Callable[..., None]) -> Callable[..., None]
        def _decorator(self, *args, **kwargs):
            # type: (GrouperHandler, *Any, **Any) -> None
            if not any(
                [
                    name == AUDIT_SECURITY and argument == perm_arg
                    for name, argument, _, _ in user_permissions(self.session, self.current_user)
                ]
            ):
                return self.forbidden()

            f(self, *args, **kwargs)

        return wraps(f)(_decorator)

    return _wrapper


def _serialize_alert(alert):
    # type: (Alert) -> Dict[str, str]
    return {"severity": alert.severity, "message": alert.message, "heading": alert.heading}


def _deserialize_alert(alert_dict):
    # type: (Dict[str, str]) -> Alert
    return Alert(
        severity=alert_dict["severity"],
        message=alert_dict["message"],
        heading=alert_dict["heading"],
    )


def _serialize_alerts(alerts):
    # type: (List[Alert]) -> str
    alert_dicts = list(map(_serialize_alert, alerts))
    alerts_json = json.dumps(alert_dicts, separators=(",", ":"))
    return quote(alerts_json)


def _deserialize_alerts(quoted_alerts_json):
    # type: (str) -> List[Alert]
    try:
        alerts_json = unquote(quoted_alerts_json)
        alert_dicts = json.loads(alerts_json)
    except ValueError:
        alert_dicts = []

    return list(map(_deserialize_alert, alert_dicts))
