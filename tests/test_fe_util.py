from datetime import datetime
from mock import patch

from grouper.fe.util import expires_when_str, long_ago_str

def test_expires_when_str():
    utcnow_fn=utcnow_fn = lambda: datetime(2015, 8, 11, 12)

    assert expires_when_str(None) == 'Never', 'no datetime means no expires'

    for date_, expected, msg in [
            ("2015-08-11 11:00:00.000", "Expired", "long before should expire"),
            ("2015-08-11 12:00:00.000", "Expired", "same time should expire"),
            ("2015-08-11 11:59:59.000", "Expired", "minute after should expire"),
            ("2015-08-11 12:00:00.100", "Expired", "milliseonds before should expire"),
            ("2015-08-11 12:00:01.000", "1 second", "singular second"),
            ("2015-08-11 12:00:02.000", "2 seconds", "pural second"),
            ("2015-08-11 12:01:02.000", "1 minute", "ignore lower periods"),
            ("2016-08-11 12:01:02.000", "1 year", "ignore lower periods"),
            ]:
        assert expires_when_str(date_, utcnow_fn=utcnow_fn) == expected, msg

def test_long_ago_str():
    utcnow_fn=utcnow_fn = lambda: datetime(2015, 8, 11, 12)
    for date_, expected, msg in [
            ("2015-08-11 11:00:00.000", "1 hour ago", "long before should expire"),
            ("2015-08-11 12:00:00.000", "now", "now"),
            ("2015-08-11 11:59:59.100", "now", "milliseonds before should be now"),
            ("2015-08-11 11:59:00.000", "1 minute ago", "1 minute"),
            ("2015-08-11 11:58:00.000", "2 minutes ago", "pural minutes"),
            ("2015-08-11 12:00:01.000", "in the future", "in the future"),
            ]:
        assert long_ago_str(date_, utcnow_fn=utcnow_fn) == expected, msg
