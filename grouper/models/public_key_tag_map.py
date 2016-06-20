from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from grouper.models.base.model_base import Model
from grouper.models.public_key_tag import PublicKeyTag


class PublicKeyTagMap(Model):
    """
    Maps a relationship between a Public Key and a Tag.
    """
    __tablename__ = "public_key_tag_map"
    __table_args__ = (
        UniqueConstraint('tag_id', 'key_id', name='uidx1'),
    )

    id = Column(Integer, primary_key=True)

    tag_id = Column(Integer, ForeignKey("public_key_tags.id"), nullable=False)
    tag = relationship(PublicKeyTag, foreign_keys=[tag_id])

    key_id = Column(Integer, ForeignKey("public_keys.id"), nullable=False)
    key = relationship("PublicKey", foreign_keys=[key_id])

    granted_on = Column(DateTime, default=datetime.utcnow, nullable=False)

    @staticmethod
    def get(session, id=None):
        # type: (Session, int) -> PublicKeyTagMap
        if id is not None:
            return session.query(PublicKeyTagMap).filter_by(id=id).scalar()
        return None
