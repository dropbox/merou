import fnmatch
import functools
import logging
import random as insecure_random
import re
import subprocess
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from settings import Settings
    from typing import Any, Dict, Pattern

_TRUTHY = {"true", "yes", "1", ""}

_DB_URL_REFRESH_TIME = 0
_DB_URL_REFRESH_JITTER = 30
_DB_URL_CACHED = None
_DB_URL_LOCK = threading.Lock()


def qp_to_bool(arg):
    return arg.lower() in _TRUTHY


def get_loglevel(args, base=None):
    if base is None:
        base = logging.getLogger().level
    verbose = args.verbose * 10
    quiet = args.quiet * 10
    return base - verbose + quiet


def try_update(dct, update):
    if set(update.keys()).intersection(set(dct.keys())):
        raise Exception("Updating {} with {} would clobber keys!".format(dct, update))
    dct.update(update)


def get_auditors_group_name(settings):
    return settings.auditors_group


def get_database_url(settings, retries=3, retry_wait_seconds=1):
    """Given settings, load a database URL either from our executable source or the bare string."""
    if not settings.database_source:
        assert settings.database is not None
        return settings.database

    # Use a cached/jitter so we don't hit the script for every request.
    global _DB_URL_CACHED, _DB_URL_REFRESH_TIME, _DB_URL_REFRESH_JITTER, _DB_URL_LOCK
    with _DB_URL_LOCK:
        if _DB_URL_REFRESH_TIME > time.time() and _DB_URL_CACHED is not None:
            return _DB_URL_CACHED
        _DB_URL_REFRESH_TIME = time.time() + (insecure_random.random() * _DB_URL_REFRESH_JITTER)
        retry = 0
        while True:
            try:
                url = subprocess.check_output([settings.database_source])
                _DB_URL_CACHED = url.strip()
                return _DB_URL_CACHED
            except subprocess.CalledProcessError as e:
                logging.info("database_source: " + str(settings.database_source))
                logging.error(e)
                retry += 1
                if retry > retries:
                    raise
                time.sleep(retry_wait_seconds)


# TODO(lfaraone): Consider moving this to a LRU cache to avoid memory leaks
_regex_cache = {}  # type: Dict[str, Pattern]


def matches_glob(glob, text):
    # type: (str, str) -> bool
    """Returns True/False on if text matches glob."""
    if "*" not in glob:
        return text == glob
    try:
        regex = _regex_cache[glob]
    except KeyError:
        regex = re.compile(fnmatch.translate(glob))
        _regex_cache[glob] = regex
    return regex.match(text) is not None


def singleton(f):
    """Decorator which ensures that a function (with no arguments) is only
       called once, and then all subsequent calls return the cached return value.
    """
    lock = threading.Lock()
    initialized = [False]
    value = [None]

    @functools.wraps(f)
    def wrapped():
        if not initialized[0]:
            with lock:
                if not initialized[0]:
                    value[0] = f()
                    initialized[0] = True
        return value[0]

    return wrapped


def reference_id(settings, request_type, request):
    # type: (Settings, str, Any) -> str
    """Generates the 'References' for a request"""
    try:
        domain = settings["service_account_email_domain"]
    except KeyError:
        domain = "grouper.local"
    return "<{type}.{id}.{ts}@{prefix}.{domain}>".format(
        type=request_type,
        id=request.id,
        ts=request.requested_at.strftime("%Y%m%d%H%M%S"),
        prefix="grouper-internal",
        domain=domain,
    )
