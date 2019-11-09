import fnmatch
import functools
import logging
import re
import threading
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from argparse import Namespace
    from grouper.settings import Settings
    from typing import Any, Callable, Dict, List, Optional, Pattern

T = TypeVar("T")

_TRUTHY = {"true", "yes", "1", ""}


def get_loglevel(args, base=None):
    # type: (Namespace, Optional[int]) -> int
    if base is None:
        base = logging.getLogger().level
    verbose = args.verbose * 10
    quiet = args.quiet * 10
    return base - verbose + quiet


def try_update(dct, update):
    # type: (Dict[str, Any], Dict[str, Any]) -> None
    if set(update.keys()).intersection(set(dct.keys())):
        raise Exception("Updating {} with {} would clobber keys!".format(dct, update))
    dct.update(update)


def get_auditors_group_name(settings):
    # type: (Settings) -> str
    return settings.auditors_group


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
    # type: (Callable[[], T]) -> Callable[[], T]
    """Thread-safe global singleton.

    Decorator which ensures that a function (with no arguments) is only called once, and then all
    subsequent calls return the cached return value.
    """
    lock = threading.Lock()
    initialized = [False]
    value = [None]  # type: List[Optional[T]]

    @functools.wraps(f)
    def wrapped():
        # type: () -> T
        if not initialized[0]:
            with lock:
                if not initialized[0]:
                    value[0] = f()
                    initialized[0] = True
        assert value[0] is not None
        return value[0]

    return wrapped


def reference_id(settings, request_type, request):
    # type: (Settings, str, Any) -> str
    """Generates the 'References' for a request"""
    domain = settings.service_account_email_domain
    return "<{type}.{id}.{ts}@{prefix}.{domain}>".format(
        type=request_type,
        id=request.id,
        ts=request.requested_at.strftime("%Y%m%d%H%M%S"),
        prefix="grouper-internal",
        domain=domain,
    )
