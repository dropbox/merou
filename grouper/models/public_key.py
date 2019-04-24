from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from grouper.models.base.model_base import Model, utcnow_without_ms


class PublicKey(Model):

    __tablename__ = "public_keys"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", foreign_keys=[user_id])

    key_type = Column(String(length=32))
    key_size = Column(Integer)
    public_key = Column(Text, nullable=False)
    fingerprint = Column(String(length=64), nullable=False, unique=True)
    fingerprint_sha256 = Column(String(length=64), nullable=False, unique=True)
    created_on = Column(DateTime, default=utcnow_without_ms, nullable=False)
    comment = Column(String(length=255))
