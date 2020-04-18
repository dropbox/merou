from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import object_session


class _Model:
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

    def just_created(self, session):
        pass

    def add(self, session):
        session._add(self)
        self.just_created(session)
        return self

    def delete(self, session):
        session._delete(self)
        return self


Model = declarative_base(cls=_Model)
