import logging
import re
from argparse import ArgumentTypeError
from datetime import datetime
from functools import wraps
from typing import TYPE_CHECKING

from grouper.constants import NAME_VALIDATION, USERNAME_VALIDATION

if TYPE_CHECKING:
    from argparse import Namespace
    from datetime import date
    from grouper.ctl.settings import CtlSettings
    from grouper.repositories.factory import SessionFactory
    from typing import Callable

    CommandFunction = Callable[[Namespace, CtlSettings, SessionFactory], None]

DATE_FORMAT = "%Y-%m-%d"


def ensure_valid_username(f):
    # type: (CommandFunction) -> CommandFunction
    @wraps(f)
    def wrapper(args, settings, session_factory):
        # type: (Namespace, CtlSettings, SessionFactory) -> None
        usernames = args.username if type(args.username) == list else [args.username]
        valid = True
        for username in usernames:
            if not re.match("^{}$".format(USERNAME_VALIDATION), username):
                valid = False
                logging.error("Invalid username {}".format(username))

        if not valid:
            return

        return f(args, settings, session_factory)

    return wrapper


def ensure_valid_groupname(f):
    # type: (CommandFunction) -> CommandFunction
    @wraps(f)
    def wrapper(args, settings, session_factory):
        # type: (Namespace, CtlSettings, SessionFactory) -> None
        if not re.match("^{}$".format(NAME_VALIDATION), args.groupname):
            logging.error("Invalid group name {}".format(args.groupname))
            return

        return f(args, settings, session_factory)

    return wrapper


def argparse_validate_date(s):
    # type: (str) -> date
    """validates argparse argument is a datetime.date."""
    try:
        return datetime.strptime(s, DATE_FORMAT).date()
    except ValueError:
        raise ArgumentTypeError("not a valid date: '{}'".format(s))
