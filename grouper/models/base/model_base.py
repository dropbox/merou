from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import object_session


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

        cls.just_created(instance)

        return instance, True

    def just_created(self):
        pass

    def add(self, session):
        session._add(self)
        return self

    def delete(self, session):
        session._delete(self)
        return self


Model = declarative_base(cls=_Model)
