from functools import wraps
import logging
import re

from grouper.constants import NAME_VALIDATION, USERNAME_VALIDATION
from grouper.settings import settings
from grouper.util import get_database_url
from grouper.models.base.session import Session, get_db_engine


def ensure_valid_username(f):
    @wraps(f)
    def wrapper(args):
        usernames = args.username if type(args.username) == list else [args.username]
        valid = True
        for username in usernames:
            if not re.match("^{}$".format(USERNAME_VALIDATION), username):
                valid = False
                logging.error("Invalid username {}".format(username))

        if not valid:
            return

        return f(args)

    return wrapper


def ensure_valid_groupname(f):
    @wraps(f)
    def wrapper(args):
        if not re.match("^{}$".format(NAME_VALIDATION), args.groupname):
            logging.error("Invalid group name {}".format(args.groupname))
            return

        return f(args)

    return wrapper


def make_session():
    db_engine = get_db_engine(get_database_url(settings))
    Session.configure(bind=db_engine)
    return Session()
