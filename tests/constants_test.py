import re

from grouper.constants import USERNAME_VALIDATION


def test_username_validation() -> None:
    regex = f"^{USERNAME_VALIDATION}$"

    good_users = [
        "example@example.com",
        "jane@a.b.c.d.co",  # subdomains
        "bobby@yahoo-inc.com",  # dashes in domains
    ]
    for user in good_users:
        assert re.match(regex, user)

    bad_users = [
        "nodomain",  # no domain part
        "bad@domain",  # invalid domain part
        "foo@u.s",  # single character top-level domain
        "johnny.appleseed@a.co",  # period in username
        "jackbrown+new@a.co",  # gmail style aliases
        "example@example..com",  # doubled period
        "example@.example.com",  # period after @
    ]
    for user in bad_users:
        assert not re.match(regex, user)
