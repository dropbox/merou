from base64 import b64encode
from datetime import datetime
from hashlib import sha384
import os.path

from dateutil.relativedelta import relativedelta
from jinja2 import Environment, PackageLoader
from pytz import UTC

from grouper.fe.settings import settings


RESOURCE_INTEGRITY_VALUES = {}
CHUNK_SIZE = 1024 * 16


def get_integrity_of_static(path):
    if settings or not RESOURCE_INTEGRITY_VALUES[path]:

        resolved_file = os.path.join(os.curdir, 'grouper/fe/static', path)

        resource_hash = sha384()
        with open(resolved_file) as f:
            bytes_read = f.read(CHUNK_SIZE)
            while bytes_read:
                resource_hash.update(bytes_read)
                bytes_read = f.read(CHUNK_SIZE)

        digest = resource_hash.digest()

        RESOURCE_INTEGRITY_VALUES[path] = b64encode(digest)

    return "sha384-{hash}".format(hash=RESOURCE_INTEGRITY_VALUES[path])


def _make_date_obj(date_obj):
    """Given either a datetime object, float date/time in UTC unix epoch, or
    string date/time in the form '%Y-%m-%d %H:%M:%S.%f' return a datetime
    object."""
    if isinstance(date_obj, float):
        date_obj = datetime.fromtimestamp(date_obj, UTC)

    if isinstance(date_obj, basestring):
        date_obj = datetime.strptime(date_obj, "%Y-%m-%d %H:%M:%S.%f")
        date_obj = date_obj.replace(tzinfo=UTC)

    assert isinstance(date_obj, datetime)

    if date_obj.tzinfo is None:
        # naive dates are assumed UTC
        date_obj = date_obj.replace(tzinfo=UTC)

    return date_obj


def _utcnow():
    return datetime.now(UTC)


def print_date(date_obj):
    """Print a human readable date/time string that respects system
    configuration for time zone and date/time format.

    Args:
        date_obj(datetime, float, str): either a datetime object, float of
        seconds since epoch, or a str in the form '%Y-%m-%d %H:%M:%S.%f'

    Returns human readable date/time string.
    """
    if date_obj is None:
        return ""

    date_obj = _make_date_obj(date_obj)

    date_obj = date_obj.astimezone(settings["timezone"])
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


def get_template_env(package="grouper.fe", deployment_name="",
                     extra_filters=None, extra_globals=None):
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
        "get_integrity_of_static": get_integrity_of_static,
    }

    if extra_filters:
        filters.update(extra_filters)
    if extra_globals:
        j_globals.update(extra_globals)

    env = Environment(loader=PackageLoader(package, "templates"))
    env.filters.update(filters)
    env.globals.update(j_globals)

    return env
