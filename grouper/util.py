import fnmatch
import functools
import logging
import random as insecure_random
import subprocess
import threading
import time

_TRUTHY = set([
    "true", "yes", "1", ""
])

_DB_URL_REFRESH_TIME = 0
_DB_URL_REFRESH_JITTER = 30
_DB_URL_CACHED = None
_DB_URL_LOCK = threading.Lock()


def qp_to_bool(arg):
    return arg.lower() in _TRUTHY


def get_loglevel(args):
    verbose = args.verbose * 10
    quiet = args.quiet * 10
    return logging.getLogger().level - verbose + quiet


def try_update(dct, update):
    if set(update.keys()).intersection(set(dct.keys())):
        raise Exception("Updating {} with {} would clobber keys!".format(dct, update))
    dct.update(update)


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


def matches_glob(glob, text):
    """Returns True/False on if text matches glob."""
    return fnmatch.fnmatch(text, glob)


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
