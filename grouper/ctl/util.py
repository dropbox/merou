import logging
import re
from argparse import ArgumentTypeError
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from sys import stdout
from typing import TYPE_CHECKING

from grouper.constants import NAME_VALIDATION, SERVICE_ACCOUNT_VALIDATION, USERNAME_VALIDATION
from grouper.models.base.session import get_db_engine, Session

if TYPE_CHECKING:
    from argparse import Namespace
    from datetime import date
    from grouper.ctl.settings import CtlSettings
    from typing import Callable, Generator

DATE_FORMAT = "%Y-%m-%d"


def ensure_valid_username(f):
    # type: (Callable[[Namespace, CtlSettings], None]) -> Callable[[Namespace, CtlSettings], None]
    @wraps(f)
    def wrapper(args, settings):
        # type: (Namespace, CtlSettings) -> None
        usernames = args.username if type(args.username) == list else [args.username]
        valid = True
        for username in usernames:
            if not re.match("^{}$".format(USERNAME_VALIDATION), username):
                valid = False
                logging.error("Invalid username {}".format(username))

        if not valid:
            return

        return f(args, settings)

    return wrapper


def ensure_valid_groupname(f):
    # type: (Callable[[Namespace, CtlSettings], None]) -> Callable[[Namespace, CtlSettings], None]
    @wraps(f)
    def wrapper(args, settings):
        # type: (Namespace, CtlSettings) -> None
        if not re.match("^{}$".format(NAME_VALIDATION), args.groupname):
            logging.error("Invalid group name {}".format(args.groupname))
            return

        return f(args, settings)

    return wrapper


def ensure_valid_service_account_name(f):
    # type: (Callable[[Namespace, CtlSettings], None]) -> Callable[[Namespace, CtlSettings], None]
    @wraps(f)
    def wrapper(args, settings):
        # type: (Namespace, CtlSettings) -> None
        if not re.match("^{}$".format(SERVICE_ACCOUNT_VALIDATION), args.name):
            logging.error('Invalid service account name "{}"'.format(args.name))
            return

        return f(args, settings)

    return wrapper


def make_session(settings):
    # type: (CtlSettings) -> Session
    db_engine = get_db_engine(settings.database_url)
    Session.configure(bind=db_engine)
    return Session()


def argparse_validate_date(s):
    # type: (str) -> date
    """validates argparse argument is a datetime.date."""
    try:
        return datetime.strptime(s, DATE_FORMAT).date()
    except ValueError:
        raise ArgumentTypeError("not a valid date: '{}'".format(s))


@contextmanager
def open_file(fn, mode):
    # type: (str, str) -> Generator
    """mimic standard library `open` function to support stdout if None is
    specified as the filename."""
    if fn and fn != "--":
        fh = open(fn, mode)
    else:
        fh = stdout  # type: ignore

    try:
        yield fh
    finally:
        if fh is not stdout:
            fh.close()
