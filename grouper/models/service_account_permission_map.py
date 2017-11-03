from collections import defaultdict, namedtuple
from datetime import datetime
from typing import Dict, List  # noqa

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from grouper.constants import MAX_NAME_LENGTH
from grouper.models.base.model_base import Model
from grouper.models.base.session import Session  # noqa
from grouper.models.permission import Permission
from grouper.models.service_account import ServiceAccount
from grouper.models.user import User

# A single permission.  "distance" is always 0 but simplifies some UI logic if present.
ServiceAccountPermission = namedtuple("ServiceAccountPermission",
    ["permission", "argument", "granted_on", "mapping_id"])


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

    argument = Column(String(length=MAX_NAME_LENGTH), nullable=True)
    granted_on = Column(DateTime, default=datetime.utcnow, nullable=False)

    @staticmethod
    def all_permissions(session):
        # type: (Session) -> Dict[str, List[ServiceAccountPermission]]
        """Return a dict of service account names to their permissions."""
        out = defaultdict(list)  # type: Dict[str, List[ServiceAccountPermission]]
        permissions = session.query(Permission, ServiceAccountPermissionMap).filter(
            Permission.id == ServiceAccountPermissionMap.permission_id,
            ServiceAccountPermissionMap.service_account_id == ServiceAccount.id,
            ServiceAccount.user_pk == User.id,
            User.enabled == True,
        )
        for permission in permissions:
            out[permission[1].service_account.user.username].append(ServiceAccountPermission(
                permission=permission[0].name,
                argument=permission[1].argument,
                granted_on=permission[1].granted_on,
                mapping_id=permission[1].id,
            ))
        return out

    @staticmethod
    def get(session, id=None):
        # type: (Session, int) -> ServiceAccountPermissionMap
        if id is not None:
            return session.query(ServiceAccountPermissionMap).filter_by(id=id).scalar()
        return None

    @staticmethod
    def permissions_for(session, service_account):
        # type: (Session, ServiceAccount) -> List[ServiceAccountPermission]
        """Return the permissions of a service account."""
        permissions = session.query(Permission, ServiceAccountPermissionMap).filter(
            Permission.id == ServiceAccountPermissionMap.permission_id,
            ServiceAccountPermissionMap.service_account_id == service_account.id,
            ServiceAccountPermissionMap.service_account_id == ServiceAccount.id,
            ServiceAccount.user_pk == User.id,
            User.enabled == True,
        )
        out = []
        for permission in permissions:
            out.append(ServiceAccountPermission(
                permission=permission[0].name,
                argument=permission[1].argument,
                granted_on=permission[1].granted_on,
                mapping_id=permission[1].id
            ))
        return out
