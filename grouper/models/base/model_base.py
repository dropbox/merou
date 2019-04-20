from datetime import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import object_session


def utcnow_without_ms():
    # type: () -> datetime
    """Return the current time without microseconds.

    This is used as a default value for creation dates for database rows.  Trying to store
    microseconds in the database has varying results depending on the database backend (MySQL
    strips them, SQLite stores them), which in turn can cause test failures because the
    pre-committed object and the object read from the database don't match.  Grouper has no need of
    sub-second timestamp accuracy, so simplify things by using this function.
    """
    return datetime.utcnow().replace(microsecond=0)


class _Model(object):
    """ Custom model mixin with helper methods. """

    @property
    def session(self):
        return object_session(self)

    @classmethod
    def get(cls, session, **kwargs):
        instance = session.query(cls).filter_by(**kwargs).scalar()
        if instance:
            return instance
        return None

    @classmethod
    def get_or_create(cls, session, **kwargs):
        instance = session.query(cls).filter_by(**kwargs).scalar()
        if instance:
            return instance, False

        instance = cls(**kwargs)
        instance.add(session)

        return instance, True

    def just_created(self):
        pass

    def add(self, session):
        session._add(self)
        self.just_created()
        return self

    def delete(self, session):
        session._delete(self)
        return self


Model = declarative_base(cls=_Model)
