from datetime import datetime

from pytz import UTC

from grouper.settings import Settings
from grouper.templating import BaseTemplateEngine


def mock_utcnow():
    # type: () -> datetime
    return datetime(2015, 8, 11, 12, tzinfo=UTC)


def test_expires_when_str():
    # type: () -> None
    assert BaseTemplateEngine.expires_when_str(None) == "Never", "no datetime means no expires"

    for date, expected, msg in [
        (datetime(2015, 8, 11, 11, 00, 00, 0), "Expired", "long before should expire"),
        (datetime(2015, 8, 11, 12, 00, 00, 0), "Expired", "same time should expire"),
        (datetime(2015, 8, 11, 11, 59, 59, 0), "Expired", "minute after should expire"),
        (datetime(2015, 8, 11, 12, 0, 0, 100), "Expired", "milliseonds should be ignored"),
        (datetime(2015, 8, 11, 12, 0, 1, 0), "1 second", "singular second"),
        (datetime(2015, 8, 11, 12, 0, 2, 0), "2 seconds", "pural second"),
        (datetime(2015, 8, 11, 12, 1, 2, 0), "1 minute", "ignore lower periods"),
        (datetime(2016, 8, 11, 12, 1, 2, 0), "1 year", "ignore lower periods"),
    ]:
        utcdate = date.replace(tzinfo=UTC)
        assert BaseTemplateEngine.expires_when_str(utcdate, utcnow_fn=mock_utcnow) == expected, msg
        assert BaseTemplateEngine.expires_when_str(date, utcnow_fn=mock_utcnow) == expected, (
            msg + " (no tzinfo)"
        )


def test_long_ago_str():
    # type: () -> None
    for date, expected, msg in [
        (datetime(2015, 8, 11, 11, 0, 0, 0), "1 hour ago", "long before should expire"),
        (datetime(2015, 8, 11, 12, 0, 0, 0), "now", "now"),
        (datetime(2015, 8, 11, 11, 59, 59, 100), "now", "milliseconds should be ignored"),
        (datetime(2015, 8, 11, 11, 59, 0, 0), "1 minute ago", "1 minute"),
        (datetime(2015, 8, 11, 11, 58, 0, 0), "2 minutes ago", "pural minutes"),
        (datetime(2015, 8, 11, 12, 0, 1, 0), "in the future", "in the future"),
    ]:
        utcdate = date.replace(tzinfo=UTC)
        assert BaseTemplateEngine.long_ago_str(utcdate, utcnow_fn=mock_utcnow) == expected, msg
        assert BaseTemplateEngine.long_ago_str(date, utcnow_fn=mock_utcnow) == expected, (
            msg + " (no tzinfo)"
        )


def test_print_date():
    # type: () -> None
    settings = Settings()
    settings.date_format = "%Y-%m-%d %I:%M %p"
    setattr(settings, "timezone", "US/Pacific")  # work around mypy confusion
    template_engine = BaseTemplateEngine(settings, "grouper.fe")

    for date_, expected, msg in [
        (datetime(2015, 8, 11, 18, tzinfo=UTC), "2015-08-11 11:00 AM", "from datetime object"),
        (datetime(2015, 8, 11, 18, 0, 10, 10, tzinfo=UTC), "2015-08-11 11:00 AM", "ignore sec/ms"),
        (datetime(2015, 8, 11, 18, 0, 10, 10), "2015-08-11 11:00 AM", "add tzinfo if needed"),
    ]:
        assert template_engine.print_date(date_) == expected, msg
