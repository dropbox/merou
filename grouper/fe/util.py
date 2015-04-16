from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from expvar.stats import stats
from jinja2 import Environment, PackageLoader
import logging
import pytz
import re
import smtplib
import sqlalchemy.exc
import tornado.web
import traceback
import urllib

from .settings import settings
from ..constants import RESERVED_NAMES
from ..graph import Graph
from ..models import User, GROUP_EDGE_ROLES, OBJ_TYPES_IDX, get_db_engine, Session
from ..util import get_database_url


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


class GrouperHandler(tornado.web.RequestHandler):
    def initialize(self):
        self.session = self.application.my_settings.get("db_session")()
        self.graph = Graph()
        stats.incr("requests")

    def _handle_request_exception(self, e):
        traceback.print_exc()

        # We can't just self.render because that invokes get_current_user which tries to make a
        # db call, and if we're handling a db exception, that breaks.
        self.set_status(500)
        template = self.application.my_settings["template_env"].get_template("errors/5xx.html")
        self.write(template.render({"is_active": self.is_active}))
        self.finish()

    def get_current_user(self):
        username = self.request.headers.get(settings.user_auth_header)
        if not username:
            return

        # Users must be fully qualified
        if not re.match(r"[^@]+@[^@]+\.[^@]+", username):
            raise InvalidUser()

        try:
            user, created = User.get_or_create(self.session, username=username)
            if created:
                logging.info("Created new user %s", username)
                self.session.commit()
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
        self.session.close()

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

    def send_email(self, recipients, subject, template, context):
        template_env = self.application.my_settings["template_env"]
        sender = settings["from_addr"]

        context["url"] = settings["url"]

        text_template = template_env.get_template(
            "email/{}_text.tmpl".format(template)
        ).render(**context)
        html_template = template_env.get_template(
            "email/{}_html.tmpl".format(template)
        ).render(**context)

        text = MIMEText(text_template, "plain")
        html = MIMEText(html_template, "html")

        if isinstance(recipients, basestring):
            recipients = recipients.split(",")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)
        msg.attach(text)
        msg.attach(html)

        if not settings["send_emails"]:
            logging.debug(msg.as_string())
            return

        smtp = smtplib.SMTP(settings["smtp_server"])
        smtp.sendmail(sender, recipients, msg.as_string())
        smtp.quit()

    def get_form_alerts(self, errors):
        alerts = []
        for field, field_errors in errors.items():
            for error in field_errors:
                alerts.append(Alert("danger", error, field))
        return alerts

    # TODO(gary): Add json error responses.
    def badrequest(self, format_type=None):
        self.set_status(400)
        self.render("errors/badrequest.html")

    def forbidden(self, format_type=None):
        self.set_status(403)
        self.render("errors/forbidden.html")

    def notfound(self, format_type=None):
        self.set_status(404)
        self.render("errors/notfound.html")


def print_date(date_obj):
    if date_obj is None:
        return ""

    if date_obj.tzinfo is None:
        # Assume naive datetime objects are UTC
        date_obj = date_obj.replace(tzinfo=pytz.UTC)

    date_obj = date_obj.astimezone(settings["timezone"])
    return date_obj.strftime(settings["date_format"])


_DELTA_COMPONENTS = [
    ("year", 31536000),
    ("month", 2592000),
    ("day", 86400),
    ("hour", 3600),
    ("minute", 60),
    ("second", 1),
]


def delta_str(date_obj):
    if date_obj is None:
        return "Never"

    if isinstance(date_obj, basestring):
        date_obj = datetime.strptime(date_obj, "%Y-%m-%d %H:%M:%S.%f")

    delta = date_obj - datetime.utcnow()
    total_seconds = int(delta.total_seconds())

    if total_seconds < 0:
        return "Expired"

    for name, seconds in _DELTA_COMPONENTS:
        if total_seconds <= seconds:
            continue

        value, total_seconds = divmod(total_seconds, seconds)

        # Only want the highest period so return.
        return "{} {}(s)".format(value, name)

    return "Expired"


def get_template_env(package="grouper.fe", extra_filters=None, extra_globals=None):
    filters = {
        "print_date": print_date,
        "delta_str": delta_str,
    }
    j_globals = {
        "cdnjs_prefix": settings["cdnjs_prefix"],
        "ROLES": GROUP_EDGE_ROLES,
        "TYPES": OBJ_TYPES_IDX,
    }

    if extra_filters:
        filters.update(extra_filters)
    if extra_globals:
        j_globals.update(extra_globals)

    env = Environment(loader=PackageLoader(package, "templates"))
    env.filters.update(filters)
    env.globals.update(j_globals)

    return env


# Returns a list of strings explaining whcih reserved regexes match a proposed
# permission name.
def test_reserved_names(permission_name):
    failure_messages = []
    for reserved in RESERVED_NAMES:
        if re.match(reserved, permission_name):
            failure_messages.append(
                "Permission names must not match the pattern: %s" % (reserved, )
            )
    return failure_messages
