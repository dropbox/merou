from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship

from grouper.models.base.constants import REQUEST_STATUS_CHOICES
from grouper.models.base.model_base import Model
from grouper.models.comment import CommentObjectMixin
from grouper.models.user import User


class RequestStatusChange(Model, CommentObjectMixin):

    __tablename__ = "request_status_changes"

    id = Column(Integer, primary_key=True)

    request_id = Column(Integer, ForeignKey("requests.id"))
    request = relationship("Request")

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship(User, foreign_keys=[user_id])

    from_status = Column(Enum(*REQUEST_STATUS_CHOICES))
    to_status = Column(Enum(*REQUEST_STATUS_CHOICES), nullable=False)

    change_at = Column(DateTime, default=datetime.utcnow, nullable=False)
