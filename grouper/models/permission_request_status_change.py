from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from grouper.models.base.constants import REQUEST_STATUS_CHOICES
from grouper.models.base.model_base import Model
from grouper.models.comment import CommentObjectMixin


class PermissionRequestStatusChange(Model, CommentObjectMixin):
    """Tracks changes to each permission grant request."""

    __tablename__ = "permission_request_status_changes"

    id = Column(Integer, primary_key=True)

    request_id = Column(Integer, ForeignKey("permission_requests.id"), nullable=False)
    request = relationship("PermissionRequest")

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", foreign_keys=[user_id])

    from_status = Column(Enum(*REQUEST_STATUS_CHOICES))
    to_status = Column(Enum(*REQUEST_STATUS_CHOICES), nullable=False)

    change_at = Column(DateTime, default=datetime.utcnow, nullable=False)
