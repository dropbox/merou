from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from grouper.constants import MAX_NAME_LENGTH
from grouper.models.base.model_base import Model


class TagPermissionMap(Model):
    """
    Maps a relationship between a Permission and a Tag. Note that a single permission can be
    mapped into a given tag multiple times, as long as the argument is unique.

    These include the optional arguments, which can either be a string, an asterisks ("*"), or
    Null to indicate no argument.
    """
    __tablename__ = "tag_permissions_map"
    __table_args__ = (
        UniqueConstraint('permission_id', 'tag_id', 'argument', name='uidx1'),
    )

    id = Column(Integer, primary_key=True)

    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    permission = relationship("Permission", foreign_keys=[permission_id])

    tag_id = Column(Integer, ForeignKey("public_key_tags.id"), nullable=False)
    tag = relationship("PublicKeyTag", foreign_keys=[tag_id])

    argument = Column(String(length=MAX_NAME_LENGTH), nullable=True)
    granted_on = Column(DateTime, default=datetime.utcnow, nullable=False)

    @staticmethod
    def get(session, id=None):
        # type: (Session, int) -> TagPermissionMap
        if id is not None:
            return session.query(TagPermissionMap).filter_by(id=id).scalar()
        return None
