from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from dateutil.relativedelta import relativedelta
from jinja2 import Environment, PackageLoader, select_autoescape
from pytz import UTC

from grouper.entities.group_edge import GROUP_EDGE_ROLES
from grouper.models.base.constants import OBJ_TYPES_IDX

if TYPE_CHECKING:
    from jinja2 import Template
    from grouper.settings import Settings
    from typing import Callable, Optional

# Components of a relativedelta, in order from longest interval to shortest.  microseconds are
# intentionally ignored; a relativedelta with only microseconds is treated the same as zero.
DELTA_COMPONENTS = ["year", "month", "day", "hour", "minute", "second"]


def _utcnow():
    # type: () -> datetime
    return datetime.now(UTC)


class BaseTemplateEngine:
    """Lightweight wrapper around the Jinja2 template engine.

    Provides some date-formatting filters that honor global settings, and some global variables.

    This class is meant to be subclassed by each UI that uses templating, overriding __init__ to
    set any additional filters and globals that are relevant to that UI and passing in the package
    from which templates should be loaded.
    """

    def __init__(self, settings: Settings, package: str) -> None:
        self.settings = settings
        loader = PackageLoader(package, "templates")
        self.environment = Environment(loader=loader, autoescape=select_autoescape(["html"]))

        filters = {
            "expires_when_str": self.expires_when_str,
            "long_ago_str": self.long_ago_str,
            "print_date": self.print_date,
        }
        self.environment.filters.update(filters)

        template_globals = {"ROLES": GROUP_EDGE_ROLES, "TYPES": OBJ_TYPES_IDX}
        self.environment.globals.update(template_globals)

    def get_template(self, name: str) -> Template:
        return self.environment.get_template(name)

    def print_date(self, date: Optional[datetime]) -> str:
        """Format a human readable datetime string, respecting configuration settings."""
        if date is None:
            return ""
        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)
        date = date.astimezone(self.settings.timezone)
        return date.strftime(self.settings.date_format)

    @classmethod
    def expires_when_str(
        cls, date: Optional[datetime], utcnow_fn: Callable[[], datetime] = _utcnow
    ) -> str:
        """Format an expiration datetime.

        The utcnow_fn parameter is only used for testing and allows overriding the definition of
        "now" for predictable results.  The default is datetime.utcnow.
        """
        if date is None:
            return "Never"
        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)

        now = utcnow_fn()
        if now > date:
            return "Expired"

        delta = relativedelta(date, now)
        delta_str = cls._highest_period_delta_str(delta)
        if delta_str is None:
            return "Expired"
        else:
            return delta_str

    @classmethod
    def long_ago_str(cls, date: datetime, utcnow_fn: Callable[[], datetime] = _utcnow) -> str:
        """Format a datetime as an interval in the past.

        The utcnow_fn parameter is only used for testing and allows overriding the definition of
        "now" for predictable results.  The default is datetime.utcnow.
        """
        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)

        now = utcnow_fn()
        if date > now:
            return "in the future"

        delta = relativedelta(now, date)
        delta_str = cls._highest_period_delta_str(delta)
        if delta_str is None:
            return "now"
        else:
            return "{} ago".format(delta_str)

    @staticmethod
    def _highest_period_delta_str(delta: relativedelta) -> Optional[str]:
        """Return a string version of the longest non-microsecond interval in a relativedelta.

        Helper function for expires_when_str and long_ago_str.  If relativedelta is negative or
        zero, return None.  The caller is responsible for mapping a None response to a string
        representation that makes sense for the context.

        microseconds are ignored, and a relativedelta differing only in microseconds is treated the
        same as one that's zero.
        """
        for component in DELTA_COMPONENTS:
            value = getattr(delta, "{}s".format(component))
            if value > 0:
                return "{} {}{}".format(value, component, "s" if value > 1 else "")

        # relativedelta is negative or zero.
        return None
