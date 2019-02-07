from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Column, Integer, String, Text

from grouper.constants import MAX_NAME_LENGTH
from grouper.models.audit_log import AuditLog
from grouper.models.base.model_base import Model

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import List, Optional


class PublicKeyTag(Model):

    __tablename__ = "public_key_tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(length=MAX_NAME_LENGTH), unique=True)
    description = Column(Text)
    enabled = Column(Boolean, default=True)

    def my_log_entries(self):
        # type: () -> List[AuditLog]
        """Returns the 20 most recent audit log entries involving this tag

        Returns:
            a list of AuditLog entries
        """
        return AuditLog.get_entries(self.session, on_tag_id=self.id, limit=20)

    @staticmethod
    def get(session, id=None, name=None):
        # type: (Session, int, str) -> Optional[PublicKeyTag]
        if id:
            return session.query(PublicKeyTag).filter_by(id=id).scalar()
        if name:
            return session.query(PublicKeyTag).filter_by(name=name).scalar()
        return None
