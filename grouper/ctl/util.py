import re
from functools import wraps

from grouper.constants import NAME_VALIDATION, USERNAME_VALIDATION
from grouper.models import get_db_engine, Session
from grouper.settings import settings
from grouper.util import get_database_url


def ensure_valid_username(f):
    @wraps(f)
    def wrapper(args):
        if not re.match("^{}$".format(USERNAME_VALIDATION), args.username):
            print "Invalid username {}".format(args.username)
            return

        return f(args)

    return wrapper

def ensure_valid_groupname(f):
    @wraps(f)
    def wrapper(args):
        if not re.match("^{}$".format(NAME_VALIDATION), args.groupname):
            print "Invalid group name {}".format(args.groupname)
            return

        return f(args)

    return wrapper

def make_session():
    db_engine = get_db_engine(get_database_url(settings))
    Session.configure(bind=db_engine)
    return Session()
