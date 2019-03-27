from datetime import datetime

from dateutil.relativedelta import relativedelta
from jinja2 import Environment, PackageLoader
from pytz import UTC
from six import string_types

from grouper.fe.settings import settings


def _make_date_obj(input_date_obj):
    """Given either a datetime object, float date/time in UTC unix epoch, or
    string date/time in the form '%Y-%m-%d %H:%M:%S.%f' return a datetime
    object."""
    if isinstance(input_date_obj, float):
        date_obj = datetime.fromtimestamp(input_date_obj, UTC)
    elif isinstance(input_date_obj, basestring):
        try:
            date_obj = datetime.strptime(input_date_obj, "%m/%d/%Y")
        except ValueError:
            date_obj = datetime.strptime(input_date_obj, "%Y-%m-%d %H:%M:%S.%f")
    elif isinstance(input_date_obj, datetime):
        date_obj = input_date_obj
    else:
        assert False, '{}>>>{}'.format(input_date_obj, type(input_date_obj))

    assert isinstance(date_obj, datetime)

    if date_obj.tzinfo is None:
        # naive dates are assumed UTC
        date_obj = date_obj.replace(tzinfo=UTC)

    return date_obj


def _utcnow():
    return datetime.now(UTC)


def print_date(input_date):
    """Print a human readable date/time string that respects system
    configuration for time zone and date/time format.

    Args:
        date_obj(datetime, float, str): either a datetime object, float of
        seconds since epoch, or a str in the form '%Y-%m-%d %H:%M:%S.%f'

    Returns human readable date/time string.
    """
    if input_date is None or input_date == '' or isinstance(input_date, Undefined):
        return ""

    date_obj = _make_date_obj(date_obj)

    return date_obj.strftime(settings["date_format"])


def expires_when_str(date_obj, utcnow_fn=_utcnow):
    if date_obj is None:
        return "Never"

    date_obj = _make_date_obj(date_obj)
    now = utcnow_fn()

    if now > date_obj:
        return "Expired"

    delta = relativedelta(date_obj, now)
    str_ = highest_period_delta_str(delta)
    if str_ is None:
        return "Expired"
    else:
        return str_


def long_ago_str(date_obj, utcnow_fn=_utcnow):
    date_obj = _make_date_obj(date_obj)

    now = utcnow_fn()
    if date_obj > now:
        return "in the future"

    delta = relativedelta(now, date_obj)
    str_ = highest_period_delta_str(delta)
    if str_ is None:
        return "now"
    else:
        return "{} ago".format(str_)


_DELTA_COMPONENTS = ["year", "month", "day", "hour", "minute", "second"]


def highest_period_delta_str(delta):
    for name in _DELTA_COMPONENTS:
        value = getattr(delta, "{}s".format(name))
        if value > 0:
            # Only want the highest period so return.
            ret = "{} {}{}".format(value, name, "s" if value > 1 else "")
            return ret

    return None


def get_template_env(
    package="grouper.fe", deployment_name="", extra_filters=None, extra_globals=None
):
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
        "cdnjs_prefix": settings["cdnjs_prefix"],
        "deployment_name": deployment_name,
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
