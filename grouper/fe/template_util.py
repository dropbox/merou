from datetime import datetime

from dateutil.relativedelta import relativedelta
from jinja2 import Environment, PackageLoader
from pytz import UTC

from grouper.fe.settings import settings


def print_date(date_obj):
    if date_obj is None:
        return ""

    if date_obj.tzinfo is None:
        # Assume naive datetime objects are UTC
        date_obj = date_obj.replace(tzinfo=UTC)

    date_obj = date_obj.astimezone(settings["timezone"])
    return date_obj.strftime(settings["date_format"])


def expires_when_str(date_obj, utcnow_fn=datetime.utcnow):
    if date_obj is None:
        return "Never"

    if isinstance(date_obj, basestring):
        date_obj = datetime.strptime(date_obj, "%Y-%m-%d %H:%M:%S.%f")

    now = utcnow_fn()

    if now > date_obj:
        return "Expired"

    delta = relativedelta(date_obj, now)
    str_ = highest_period_delta_str(delta)
    if str_ is None:
        return "Expired"
    else:
        return str_


def long_ago_str(date_obj, utcnow_fn=datetime.utcnow):
    if isinstance(date_obj, basestring):
        date_obj = datetime.strptime(date_obj, "%Y-%m-%d %H:%M:%S.%f")

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


def get_template_env(package="grouper.fe", deployment_name="",
                     extra_filters=None, extra_globals=None):
    # TODO(herb): get around circular depdendencies; long term remove call to
    # send_async_email() from grouper.models
    from grouper.models import GROUP_EDGE_ROLES, OBJ_TYPES_IDX

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
