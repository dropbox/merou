from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import or_
from sqlalchemy.orm import aliased
from sqlalchemy.sql import label, literal

from grouper.entities.audit import AuditMemberInfo, GroupAuditInfo
from grouper.entities.group_edge import GROUP_EDGE_ROLES
from grouper.models.audit import Audit
from grouper.models.audit_member import AuditMember
from grouper.models.base.constants import OBJ_TYPES
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.user import User
from grouper.repositories.interfaces import AuditRepository

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import List, Optional


class SQLAuditRepository(AuditRepository):
    """SQL storage layer for audits."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def group_pending_audit_info(self, groupname):
        # type: (str) -> Optional[GroupAuditInfo]
        result = (
            self.session.query(Audit)
            .filter(
                Group.groupname == groupname,
                Group.id == Audit.group_id,
                Group.audit_id == Audit.id,
                Audit.complete == False,
            )
            .one_or_none()
        )
        if result:
            return GroupAuditInfo(
                id=result.id,
                complete=result.complete,
                started_at=result.started_at,
                ends_at=result.ends_at,
            )
        else:
            return None

    def _get_group_members_edge_ids(self, groupname):
        # type: (str) -> List[int]
        parent = aliased(Group)
        group_member = aliased(Group)
        user_member = aliased(User)
        now = datetime.utcnow()
        query = (
            self.session.query(label("edge_id", GroupEdge.id))
            .filter(
                parent.groupname == groupname,
                parent.enabled == True,
                parent.id == GroupEdge.group_id,
                GroupEdge.active == True,
                group_member.id == GroupEdge.member_pk,
                group_member.enabled == True,
                or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
                GroupEdge.member_type == OBJ_TYPES["Group"],
            )
            .union(
                self.session.query(label("edge_id", GroupEdge.id)).filter(
                    parent.groupname == groupname,
                    parent.enabled == True,
                    parent.id == GroupEdge.group_id,
                    GroupEdge.active == True,
                    user_member.id == GroupEdge.member_pk,
                    user_member.enabled == True,
                    or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
                    GroupEdge.member_type == OBJ_TYPES["User"],
                )
            )
        )
        return [row.edge_id for row in query.all()]

    def group_audit_members_infos(self, groupname, audit_id):
        # type: (str, int) -> List[AuditMemberInfo]
        members_edge_ids = self._get_group_members_edge_ids(groupname)
        if not members_edge_ids:
            return []

        parent = aliased(Group)
        group_member = aliased(Group)
        user_member = aliased(User)

        query = (
            self.session.query(
                label("membership_audit_id", AuditMember.id),
                label("membership_audit_status", AuditMember.status),
                label("membership_role_int", GroupEdge._role),
                label("member_name", user_member.username),
                label("member_type", literal("User")),
            )
            .filter(
                parent.groupname == groupname,
                parent.audit_id == audit_id,
                AuditMember.audit_id == parent.audit_id,
                AuditMember.edge_id == GroupEdge.id,
                GroupEdge.member_type == OBJ_TYPES["User"],
                GroupEdge.member_pk == user_member.id,
                # only those members who have not left the group after the audit started
                AuditMember.edge_id.in_(members_edge_ids),
            )
            .union(
                self.session.query(
                    label("membership_audit_id", AuditMember.id),
                    label("membership_audit_status", AuditMember.status),
                    label("membership_role_int", GroupEdge._role),
                    label("member_name", group_member.groupname),
                    label("member_type", literal("Group")),
                ).filter(
                    parent.groupname == groupname,
                    parent.audit_id == audit_id,
                    AuditMember.audit_id == parent.audit_id,
                    AuditMember.edge_id == GroupEdge.id,
                    GroupEdge.member_type == OBJ_TYPES["Group"],
                    GroupEdge.member_pk == group_member.id,
                    # only those members who have not left the group after the audit started
                    AuditMember.edge_id.in_(members_edge_ids),
                )
            )
        )

        return [
            AuditMemberInfo(
                membership_audit_id=membership_audit_id,
                membership_audit_status=membership_audit_status,
                membership_role=GROUP_EDGE_ROLES[membership_role_int],
                member_name=member_name,
                member_type=member_type,
            )
            for (
                membership_audit_id,
                membership_audit_status,
                membership_role_int,
                member_name,
                member_type,
            ) in query.all()
        ]
