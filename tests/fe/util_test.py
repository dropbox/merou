from datetime import datetime

import pytz
from pytz import UTC

from grouper.fe.template_util import expires_when_str, long_ago_str, print_date
from grouper.settings import set_global_settings, Settings


def test_expires_when_str():
    utcnow_fn = utcnow_fn = lambda: datetime(2015, 8, 11, 12, tzinfo=UTC)

    assert expires_when_str(None) == "Never", "no datetime means no expires"

    for date, expected, msg in [
        (datetime(2015, 8, 11, 11, 00, 00, 0, tzinfo=UTC), "Expired", "long before should expire"),
        (datetime(2015, 8, 11, 12, 00, 00, 0, tzinfo=UTC), "Expired", "same time should expire"),
        (
            datetime(2015, 8, 11, 11, 59, 59, 0, tzinfo=UTC),
            "Expired",
            "minute after should expire",
        ),
        (
            datetime(2015, 8, 11, 12, 0, 0, 100, tzinfo=UTC),
            "Expired",
            "milliseonds before should expire",
        ),
        (datetime(2015, 8, 11, 12, 0, 1, 0, tzinfo=UTC), "1 second", "singular second"),
        (datetime(2015, 8, 11, 12, 0, 2, 0, tzinfo=UTC), "2 seconds", "pural second"),
        (datetime(2015, 8, 11, 12, 1, 2, 0, tzinfo=UTC), "1 minute", "ignore lower periods"),
        (datetime(2016, 8, 11, 12, 1, 2, 0, tzinfo=UTC), "1 year", "ignore lower periods"),
    ]:
        assert expires_when_str(date, utcnow_fn=utcnow_fn) == expected, msg


def test_long_ago_str():
    utcnow_fn = utcnow_fn = lambda: datetime(2015, 8, 11, 12, tzinfo=UTC)

    for date, expected, msg in [
        (
            datetime(2015, 8, 11, 11, 0, 0, 0, tzinfo=UTC),
            "1 hour ago",
            "long before should expire",
        ),
        (datetime(2015, 8, 11, 12, 0, 0, 0, tzinfo=UTC), "now", "now"),
        (
            datetime(2015, 8, 11, 11, 59, 59, 100, tzinfo=UTC),
            "now",
            "milliseconds before should be now",
        ),
        (datetime(2015, 8, 11, 11, 59, 0, 0, tzinfo=UTC), "1 minute ago", "1 minute"),
        (datetime(2015, 8, 11, 11, 58, 0, 0, tzinfo=UTC), "2 minutes ago", "pural minutes"),
        (datetime(2015, 8, 11, 12, 0, 1, 0, tzinfo=UTC), "in the future", "in the future"),
    ]:
        assert long_ago_str(date, utcnow_fn=utcnow_fn) == expected, msg


def test_print_date():
    # type: () -> None
    settings = Settings()
    settings.date_format = "%Y-%m-%d %I:%M %p"
    settings.timezone = "US/Pacific"
    settings._timezone_object = pytz.timezone("US/Pacific")
    set_global_settings(settings)

    for date_, expected, msg in [
        (datetime(2015, 8, 11, 18, tzinfo=UTC), "2015-08-11 11:00 AM", "from datetime object"),
        (datetime(2015, 8, 11, 18, 0, 10, 10, tzinfo=UTC), "2015-08-11 11:00 AM", "ignore sec/ms"),
    ]:
        assert print_date(date_) == expected, msg
