import functools
import logging
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as _Session, sessionmaker

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine


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
    return create_engine(url, pool_recycle=300)


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
