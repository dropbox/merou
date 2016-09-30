from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from grouper.models.base.model_base import Model


class Counter(Model):

    __tablename__ = "counters"

    id = Column(Integer, primary_key=True)
    name = Column(String(length=255), unique=True, nullable=False)
    count = Column(Integer, nullable=False, default=0)
    last_modified = Column(DateTime, default=datetime.utcnow, nullable=False)

    @classmethod
    def incr(cls, session, name, count=1):
        counter = session.query(cls).filter_by(name=name).scalar()
        if counter is None:
            counter = cls(name=name, count=count).add(session)
        else:
            counter.count = cls.count + count
            # TODO(herb): reenable after it's safe
            # counter.last_modified = datetime.utcnow()

        session.flush()
        return counter

    @classmethod
    def decr(cls, session, name, count=1):
        return cls.incr(session, name, -count)
