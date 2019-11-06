from typing import TYPE_CHECKING

from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.orm import backref, relationship

from grouper.models.base.model_base import Model
from grouper.models.counter import Counter
from grouper.models.user import User

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Optional


class ServiceAccount(Model):
    """Represents a group-owned service account.

    A service account is like a Grouper user, but with some key differences:

    1. Service accounts cannot take actions in Grouper and cannot be members of groups.
    2. Every service account is owned by one group.
    3. Service accounts do not inherit group permissions by default.
    4. Group members can manage the service account and delegate permissions to it.
    5. Service accounts have some additional metadata.

    Internally, a service account is represented by a ServiceAccount object pointing to a User
    object that has the service_account flag set to True.

    This data model is a compromise to avoid a large data migration.  In an ideal world, there
    would be an underlying Account object that holds the data in common between User and
    ServiceAccount, and User and ServiceAccount would both have one-to-one mappings to an Account.
    The Grouper API is set up to behave as if this world existed.
    """

    __tablename__ = "service_accounts"

    id = Column(Integer, primary_key=True)
    description = Column(Text)
    machine_set = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", uselist=False, backref=backref("service_account", uselist=False))

    def __repr__(self):
        # type: () -> str
        return "<%s: id=%s user_id=%s>" % (type(self).__name__, self.id, self.user_id)

    @staticmethod
    def get(session, pk=None, name=None):
        # type: (Session, int, str) -> Optional[ServiceAccount]
        if pk is not None:
            return session.query(ServiceAccount).filter_by(id=pk).scalar()
        if name is not None:
            return (
                session.query(ServiceAccount)
                .filter(ServiceAccount.user_id == User.id, User.username == name)
                .scalar()
            )
        return None

    def add(self, session):
        # type: (Session) -> ServiceAccount
        super().add(session)
        Counter.incr(session, "updates")
        return self
