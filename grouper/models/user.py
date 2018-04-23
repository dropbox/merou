from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

from grouper.constants import MAX_NAME_LENGTH
from grouper.models.base.model_base import Model
from grouper.models.comment import CommentObjectMixin
from grouper.models.counter import Counter
from grouper.plugin import get_plugin_proxy

if TYPE_CHECKING:
    from typing import Iterable, Optional, Tuple  # noqa
    from grouper.models.base.session import Session  # noqa


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
        # type: () -> str
        return self.username

    @property
    def type(self):
        # type: () -> str
        return "User"

    def __repr__(self):
        # type: () -> str
        return "<%s: id=%s username=%s>" % (
            type(self).__name__, self.id, self.username)

    @staticmethod
    def get(session, pk=None, name=None):
        # type: (Session, Optional[int], Optional[str]) -> Optional[User]
        if pk is not None:
            return session.query(User).filter_by(id=pk).scalar()
        if name is not None:
            return session.query(User).filter_by(username=name).scalar()
        return None

    def just_created(self):
        # type: () -> None
        """Call the user_created plugin on new User creation."""
        # This is a little weird because the default value of the column isn't applied in the
        # object at the time this is called, so role_user may be None instead of False.
        is_service_account = self.role_user is not None and self.role_user
        get_plugin_proxy().user_created(self, is_service_account)

    def add(self, session):
        # type: (Session) -> User
        super(User, self).add(session)
        Counter.incr(session, "updates")
        return self

    def is_member(self, members):
        # type: (Iterable[Tuple[str, str]]) -> bool
        return ("User", self.name) in members
