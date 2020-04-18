from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.ext.hybrid import hybrid_property

from grouper.constants import MAX_NAME_LENGTH
from grouper.models.base.model_base import Model
from grouper.models.comment import CommentObjectMixin
from grouper.models.counter import Counter
from grouper.plugin import get_plugin_proxy

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Iterable, Optional, Tuple


class User(Model, CommentObjectMixin):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(length=MAX_NAME_LENGTH), unique=True, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    role_user = Column(Boolean, default=False, nullable=False)
    is_service_account = Column(Boolean, default=False, nullable=False)

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
        return "<%s: id=%s username=%s>" % (type(self).__name__, self.id, self.username)

    @staticmethod
    def get(session, pk=None, name=None):
        # type: (Session, Optional[int], Optional[str]) -> Optional[User]
        if pk is not None:
            return session.query(User).filter_by(id=pk).scalar()
        if name is not None:
            return session.query(User).filter_by(username=name).scalar()
        return None

    def just_created(self, session):
        # type: (Session) -> None
        """Call the user_created plugin on new User creation."""
        # Flush the session to apply defaults, allocate an id, and so forth
        # in case any plugins rely on that data.
        session.flush()
        get_plugin_proxy().user_created(self, self.is_service_account)

    def add(self, session):
        # type: (Session) -> User
        super().add(session)
        Counter.incr(session, "updates")
        return self

    def is_member(self, members):
        # type: (Iterable[Tuple[str, str]]) -> bool
        return ("User", self.name) in members
