from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from grouper.constants import MAX_ARGUMENT_LENGTH
from grouper.models.base.model_base import Model

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Optional


class ServiceAccountPermissionMap(Model):
    """Relationship between Permission and ServiceAccount.

    Maps a relationship between a Permission and a ServiceAccount (compare PermissionMap for
    Group). Note that a single permission can be mapped into a given group multiple times, as long
    as the argument is unique.

    These include the optional arguments, which can either be a string, an asterisks ("*"), or
    Null to indicate no argument.
    """

    __tablename__ = "service_account_permissions_map"
    __table_args__ = (
        UniqueConstraint("permission_id", "service_account_id", "argument", name="uidx1"),
    )

    id = Column(Integer, primary_key=True)

    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    permission = relationship("Permission", foreign_keys=[permission_id])

    service_account_id = Column(Integer, ForeignKey("service_accounts.id"), nullable=False)
    service_account = relationship("ServiceAccount", foreign_keys=[service_account_id])

    argument = Column(String(length=MAX_ARGUMENT_LENGTH), nullable=True)
    granted_on = Column(DateTime, default=datetime.utcnow, nullable=False)

    @staticmethod
    def get(session, id=None):
        # type: (Session, int) -> Optional[ServiceAccountPermissionMap]
        if id is not None:
            return session.query(ServiceAccountPermissionMap).filter_by(id=id).scalar()
        return None
