from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from grouper.models.base.model_base import Model


class Audit(Model):
    # TODO: Extract business logic from this class
    # PLEASE DON'T ADD NEW BUSINESS LOGIC HERE IF YOU CAN AVOID IT!

    """An Audit is applied to a group for a particular audit period

    This contains all of the state of a given audit including each of the members who were
    present in the group at the beginning of the audit period.
    """

    __tablename__ = "audits"

    id = Column(Integer, primary_key=True)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group = relationship("Group", foreign_keys=[group_id])

    # If this audit is complete and when it started/ended
    complete = Column(Boolean, default=False, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ends_at = Column(DateTime, nullable=False)

    # Tracks the last time we emailed the responsible parties of this audit
    last_reminder_at = Column(DateTime, nullable=True)
