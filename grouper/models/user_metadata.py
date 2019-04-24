from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from grouper.models.base.model_base import Model, utcnow_without_ms


class UserMetadata(Model):

    __tablename__ = "user_metadata"
    __table_args__ = (UniqueConstraint("user_id", "data_key", name="uidx1"),)

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", foreign_keys=[user_id])

    data_key = Column(String(length=64), nullable=False)
    data_value = Column(String(length=64), nullable=False)
    last_modified = Column(DateTime, default=utcnow_without_ms, nullable=False)
