from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from grouper.models.base.model_base import Model


class PublicKey(Model):

    __tablename__ = "public_keys"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", foreign_keys=[user_id])

    key_type = Column(String(length=32))
    key_size = Column(Integer)
    public_key = Column(Text, nullable=False, unique=True)
    fingerprint = Column(String(length=64), nullable=False)
    created_on = Column(DateTime, default=datetime.utcnow, nullable=False)
