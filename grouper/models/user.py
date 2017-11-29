import logging

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from grouper.constants import MAX_NAME_LENGTH
from grouper.models.base.model_base import Model
from grouper.models.comment import CommentObjectMixin
from grouper.models.counter import Counter
from grouper.plugin import get_plugins


class User(Model, CommentObjectMixin):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(length=MAX_NAME_LENGTH), unique=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    role_user = Column(Boolean, default=False, nullable=False)
    is_service_account = Column(Boolean, default=False, nullable=False)
    tokens = relationship("UserToken", back_populates="user")

    @hybrid_property
    def name(self):
        return self.username

    @property
    def type(self):
        return "User"

    def __repr__(self):
        return "<%s: id=%s username=%s>" % (
            type(self).__name__, self.id, self.username)

    @staticmethod
    def get(session, pk=None, name=None):
        if pk is not None:
            return session.query(User).filter_by(id=pk).scalar()
        if name is not None:
            return session.query(User).filter_by(username=name).scalar()
        return None

    def just_created(self):
        for plugin in get_plugins():
            plugin.user_created(self)

    def add(self, session):
        super(User, self).add(session)
        Counter.incr(session, "updates")
        return self

    def is_member(self, members):
        return ("User", self.name) in members

    def set_metadata(self, key, value):
        from grouper.user_metadata import set_user_metadata

        logging.warning("User.set_metadata is deprecated."
            "Please switch to using grouper.user_metadata.set_user_metadata")
        set_user_metadata(self.session, self.id, key, value)
