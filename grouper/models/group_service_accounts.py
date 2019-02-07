from sqlalchemy import Column, ForeignKey, Index, Integer
from sqlalchemy.orm import backref, relationship

from grouper.models.base.model_base import Model


class GroupServiceAccount(Model):
    """Service accounts owned by a group.

    A group may own zero or more service accounts. This table holds the mapping between a Group and
    the ServiceAccount objects it owns.
    """

    __tablename__ = "group_service_accounts"
    __table_args__ = (
        Index("group_service_account_idx", "group_id", "service_account_id", unique=True),
    )

    id = Column(Integer, primary_key=True)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group = relationship("Group", backref="service_accounts", foreign_keys=[group_id])

    service_account_id = Column(Integer, ForeignKey("service_accounts.id"), nullable=False)
    service_account = relationship(
        "ServiceAccount",
        backref=backref("owner", uselist=False),
        foreign_keys=[service_account_id],
    )

    def __repr__(self):
        # type: () -> str
        return "%s(group_id=%s, service_account_id=%s)" % (
            type(self).__name__,
            self.group_id,
            self.service_account_id,
        )
