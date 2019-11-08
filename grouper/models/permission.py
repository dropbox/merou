from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from grouper.constants import MAX_NAME_LENGTH
from grouper.models.base.model_base import Model

if TYPE_CHECKING:
    from grouper.models.base.session import Session


class Permission(Model):
    """Represents permission types.

    See PermissionEdge for the mapping of which permissions exist on a given Group.
    """

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)

    name = Column(String(length=MAX_NAME_LENGTH), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    created_on = Column(DateTime, default=datetime.utcnow, nullable=False)
    audited = Column(Boolean, default=False, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    @staticmethod
    def get(session: Session, name: str) -> Permission:
        return session.query(Permission).filter_by(name=name).scalar()
