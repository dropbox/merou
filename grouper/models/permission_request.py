from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime
from sqlalchemy.orm import relationship

from grouper.models.base.constants import REQUEST_STATUS_CHOICES
from grouper.models.base.model_base import Model


class PermissionRequest(Model):
    """Represent request for a permission/argument to be granted to a particular group."""
    __tablename__ = "permission_requests"

    id = Column(Integer, primary_key=True)

    # The User that made the request.
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requester = relationship(
        "User", backref="permission_requests", foreign_keys=[requester_id]
    )

    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    permission = relationship("Permission", foreign_keys=[permission_id])
    argument = Column(String(length=64), nullable=True)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group = relationship("Group", foreign_keys=[group_id])

    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    status = Column(Enum(*REQUEST_STATUS_CHOICES), default="pending", nullable=False)
