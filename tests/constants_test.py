import re

from grouper.constants import SERVICE_ACCOUNT_VALIDATION, USERNAME_VALIDATION


def test_username_validation() -> None:
    user_regex = f"^{USERNAME_VALIDATION}$"
    service_regex = f"^{SERVICE_ACCOUNT_VALIDATION}$"

    good_users = [
        "example@example.com",
        "jane@a.b.c.d.co",  # subdomains
        "bobby@yahoo-inc.com",  # dashes in domains
        "under_sco_re@a.co",  # underscores
    ]
    for user in good_users:
        match = re.match(user_regex, user)
        assert match
        assert match.group("name") == user
        match = re.match(service_regex, user)
        assert match
        assert match.group("accountname") == user

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
        assert not re.match(user_regex, user)
        assert not re.match(service_regex, user)
