from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from grouper.constants import MAX_ARGUMENT_LENGTH
from grouper.models.base.constants import REQUEST_STATUS_CHOICES
from grouper.models.base.model_base import Model
from grouper.settings import settings
from grouper.util import reference_id


class PermissionRequest(Model):
    """Represent request for a permission/argument to be granted to a particular group."""

    __tablename__ = "permission_requests"

    id = Column(Integer, primary_key=True)

    # The User that made the request.
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requester = relationship("User", backref="permission_requests", foreign_keys=[requester_id])

    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    permission = relationship("Permission", foreign_keys=[permission_id])
    argument = Column(String(length=MAX_ARGUMENT_LENGTH), nullable=True)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group = relationship("Group", foreign_keys=[group_id])

    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    status = Column(Enum(*REQUEST_STATUS_CHOICES), default="pending", nullable=False)

    @property
    def reference_id(self):
        # type: () -> str
        return reference_id(settings(), "permission", self)
