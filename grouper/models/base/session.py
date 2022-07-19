import functools
import hashlib
import logging
from threading import Lock
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.exc import ArgumentError, OperationalError
from sqlalchemy.orm import Session as _Session, sessionmaker

from grouper.settings import InvalidSettingsError
from grouper.util import singleton

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
    from typing import Dict


def flush_transaction(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        dryrun = kwargs.pop("dryrun", False)
        try:
            ret = method(self, *args, **kwargs)
            if dryrun:
                self.session.rollback()
            else:
                self.session.flush()
        except Exception:
            logging.exception("Transaction Failed. Rolling back.")
            if self.session is not None:
                self.session.rollback()
            raise
        return ret

    return wrapper


def get_db_engine(url):
    # type: (str) -> Engine
    try:
        if "sqlite:" in url.lower():
            engine = create_engine(url, pool_recycle=300)
        else:
            engine = create_engine(url, max_overflow=25, pool_recycle=300)
    except (ArgumentError, OperationalError):
        logging.exception("Can't create database engine.")
        raise InvalidSettingsError("Invalid arguments. Can't create database engine")
    return engine


class SessionWithoutAdd(_Session):
    """Custom session to block add and add_all.

    This Session overrides the add/add_all methods to prevent them from being used. This is to
    force using the add methods on the models themselves where overriding is available.
    """

    _add = _Session.add
    _add_all = _Session.add_all
    _delete = _Session.delete

    def add(self, *args, **kwargs):
        raise NotImplementedError("Use add method on models instead.")

    def add_all(self, *args, **kwargs):
        raise NotImplementedError("Use add method on models instead.")

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Use delete method on models instead.")


Session = sessionmaker(class_=SessionWithoutAdd)


@singleton
def DbEngineManager():
    # type: () -> _DbEngineManager
    return _DbEngineManager()


class _DbEngineManager:
    """The cached database engine manager that initializates and stores SqlAlchemy engines per
    connection string. This manager provides a single database engine object per connection
    that can be accessed and re-used anywhere in the application throughout application lifecycle.

    Currently it is only used in `SessionFactory` but eventually all usages of `get_db_engine` will
    migrate to this manager.

     Attributes:
        None
    """

    def __init__(self):
        # type: () -> None
        self._engine_holder = {}  # type: Dict[str, Engine]
        self._lock = Lock()

    def get_db_engine(self, url):
        # type: (str) -> Engine
        if url not in self._engine_holder:
            with self._lock:
                if url not in self._engine_holder:
                    self._engine_holder[url] = get_db_engine(url)
                    assert self._engine_holder[url] is not None

                    logging.info(
                        f"Engine for DB url hash: {hashlib.sha256(url.encode()).hexdigest()} "
                        f"doesn't exist, creating..., engine_manager_id - "
                        f"{id(self)}, engine_id - {id(self._engine_holder[url])}"
                    )

        assert self._engine_holder[url] is not None
        return self._engine_holder[url]
