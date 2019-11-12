from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from grouper.models.base.constants import OBJ_TYPES
from grouper.models.base.model_base import Model


class CommentObjectMixin:
    """Mixin used by models which show up as objects referenced by Comment entries."""

    @property
    def member_type(self):
        obj_name = type(self).__name__
        if obj_name not in OBJ_TYPES:
            raise ValueError()  # TODO(gary) fill out error
        return OBJ_TYPES[obj_name]


class Comment(Model):

    __tablename__ = "comments"
    __table_args__ = (Index("obj_idx", "obj_type", "obj_pk", unique=False),)

    id = Column(Integer, primary_key=True)

    obj_type = Column(Integer, nullable=False)
    obj_pk = Column(Integer, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", foreign_keys=[user_id])

    comment = Column(Text, nullable=False)

    created_on = Column(
        DateTime, default=datetime.utcnow, onupdate=func.current_timestamp(), nullable=False
    )
