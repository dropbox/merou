from datetime import datetime
from typing import TYPE_CHECKING

from dateutil.relativedelta import relativedelta
from jinja2 import Environment, PackageLoader, select_autoescape
from pytz import UTC

from grouper.fe.settings import settings

if TYPE_CHECKING:
    from typing import Any, Callable, Dict, Optional

# Components of a relativedelta, in order from longest interval to shortest.  microseconds are
# intentionally ignored; a relativedelta with only microseconds is treated the same as zero.
DELTA_COMPONENTS = ["year", "month", "day", "hour", "minute", "second"]


def _highest_period_delta_str(delta):
    # type: (relativedelta) -> Optional[str]
    """Return a string version of the longest non-microsecond interval in a relativedelta.

    If relativedelta is negative or zero, return None.  The caller is responsible for mapping a
    None response to a string representation that makes sense for the context.

    microseconds are ignored, and a relativedelta differing only in microseconds is treated the
    same as one that's zero.
    """
    for component in DELTA_COMPONENTS:
        value = getattr(delta, "{}s".format(component))
        if value > 0:
            return "{} {}{}".format(value, component, "s" if value > 1 else "")

    # relativedelta is negative or zero.
    return None


def print_date(date):
    # type: (Optional[datetime]) -> str
    """Format a human readable datetime string, respecting configuration settings."""
    if date is None:
        return ""
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)
    date = date.astimezone(settings().timezone)
    return date.strftime(settings().date_format)


def _utcnow():
    # type: () -> datetime
    return datetime.now(UTC)


def expires_when_str(date, utcnow_fn=_utcnow):
    # type: (Optional[datetime], Callable[[], datetime]) -> str
    """Format an expiration datetime."""
    if date is None:
        return "Never"
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)

    now = utcnow_fn()
    if now > date:
        return "Expired"

    delta = relativedelta(date, now)
    delta_str = _highest_period_delta_str(delta)
    if delta_str is None:
        return "Expired"
    else:
        return delta_str


def long_ago_str(date, utcnow_fn=_utcnow):
    # type: (datetime, Callable[[], datetime]) -> str
    """Format a datetime as an interval in the past."""
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)

    now = utcnow_fn()
    if date > now:
        return "in the future"

    delta = relativedelta(now, date)
    delta_str = _highest_period_delta_str(delta)
    if delta_str is None:
        return "now"
    else:
        return "{} ago".format(delta_str)


def get_template_env(
    package="grouper.fe",  # type: str
    deployment_name="",  # type: str
    extra_filters=None,  # type: Optional[Dict[str, Callable[..., Any]]]
    extra_globals=None,  # type: Optional[Dict[str, Any]]
):
    # type: (...) -> Environment
    # TODO(herb): get around circular depdendencies; long term remove call to
    # send_async_email() from grouper.models
    from grouper.models.base.constants import OBJ_TYPES_IDX
    from grouper.models.group_edge import GROUP_EDGE_ROLES

    filters = {
        "print_date": print_date,
        "expires_when_str": expires_when_str,
        "long_ago_str": long_ago_str,
    }
    j_globals = {
        "deployment_name": deployment_name,
        "ROLES": GROUP_EDGE_ROLES,
        "TYPES": OBJ_TYPES_IDX,
    }

    if extra_filters:
        filters.update(extra_filters)
    if extra_globals:
        j_globals.update(extra_globals)

    env = Environment(
        loader=PackageLoader(package, "templates"), autoescape=select_autoescape(["html"])
    )
    env.filters.update(filters)
    env.globals.update(j_globals)

    return env
