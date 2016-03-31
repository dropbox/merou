from datetime import datetime
from sqlalchemy import Column, Integer, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from grouper.models.base.model_base import Model


class Comment(Model):

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)

    obj_type = Column(Integer, nullable=False)
    obj_pk = Column(Integer, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", foreign_keys=[user_id])

    comment = Column(Text, nullable=False)

    created_on = Column(DateTime, default=datetime.utcnow,
                        onupdate=func.current_timestamp(), nullable=False)
