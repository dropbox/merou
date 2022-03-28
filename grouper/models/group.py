from __future__ import annotations

import itertools
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import Boolean, Column, desc, Enum, Integer, Interval, or_, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.util import aliased
from sqlalchemy.sql import label, literal

from grouper.constants import MAX_NAME_LENGTH
from grouper.entities.group_edge import APPROVER_ROLE_INDICES, OWNER_ROLE_INDICES
from grouper.group_member import persist_group_member_changes
from grouper.models.audit import Audit
from grouper.models.audit_log import AuditLog
from grouper.models.base.constants import OBJ_TYPES_IDX
from grouper.models.base.model_base import Model
from grouper.models.base.session import flush_transaction
from grouper.models.comment import CommentObjectMixin
from grouper.models.counter import Counter
from grouper.models.group_edge import GroupEdge
from grouper.models.permission import Permission
from grouper.models.permission_map import PermissionMap
from grouper.models.user import User

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.models.request import Request
    from typing import Mapping, List, Optional, Tuple, Union

GROUP_JOIN_CHOICES = {
    # Anyone can join with automatic approval
    "canjoin": "actioned",
    # Anyone can ask to join this group
    "canask": "pending",
    # Only those invited may join (should never be a valid status because no
    # join request should be generated for such groups!)
    "nobody": "<integrityerror>",
}


class Group(Model, CommentObjectMixin):
    # TODO: Extract business logic from this class
    # PLEASE DON'T ADD NEW BUSINESS LOGIC HERE IF YOU CAN AVOID IT!

    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    groupname = Column(String(length=MAX_NAME_LENGTH), unique=True, nullable=False)
    email_address = Column(String(length=MAX_NAME_LENGTH), unique=False, nullable=True)
    description = Column(Text)
    canjoin = Column(Enum(*GROUP_JOIN_CHOICES), default="canask")
    enabled = Column(Boolean, default=True, nullable=False)
    # The default amount of time new users have before their membership in the group is expired
    # NOTE: This only applies to users who join a group via a request in the front end. It does
    # not apply to users who are added to a group by an approver
    auto_expire = Column(Interval)
    require_clickthru_tojoin = Column(Boolean, nullable=False, default=False)

    audit_id = Column(Integer, nullable=True)
    audit = relationship(
        "Audit", foreign_keys=[audit_id], primaryjoin=lambda: Audit.id == Group.audit_id
    )

    @hybrid_property
    def name(self) -> str:
        return self.groupname

    @property
    def type(self) -> str:
        return "Group"

    @flush_transaction
    def revoke_member(
        self, requester: User, user_or_group: Union[User, Group], reason: str
    ) -> None:
        """Revoke a member (User or Group) from this group.

        Args:
            requester: A User object of the person requesting the addition
            user_or_group: A User/Group object of the member
            reason: A comment on why this member should exist
        """
        logging.debug("Revoking member (%s) from %s", user_or_group.name, self.groupname)

        persist_group_member_changes(
            session=self.session,
            group=self,
            requester=requester,
            member=user_or_group,
            status="actioned",
            reason=reason,
            # Create the edge even if it doesn't exist so that we can explicitly disable it.
            create_edge=True,
            role="member",
            expiration=None,
            active=False,
        )

    def edit_member(
        self, requester: User, user_or_group: Union[User, Group], reason: str, **kwargs: Any
    ) -> None:
        """Edit an existing member (User or Group) of a group.

        This takes the same parameters as add_member, except that we do not allow you to set a
        status: this only works on existing members.

        Any option that is not passed is not updated, and instead, the existing value for this user
        is kept.
        """
        logging.debug("Editing member (%s) in %s", user_or_group.name, self.groupname)

        try:
            persist_group_member_changes(
                session=self.session,
                group=self,
                requester=requester,
                member=user_or_group,
                status="actioned",
                reason=reason,
                **kwargs,
            )
            self.session.flush()
        except Exception:
            self.session.rollback()
            raise

        member_type = user_or_group.member_type

        message = "Edit member {} {}: {}".format(
            OBJ_TYPES_IDX[member_type].lower(), user_or_group.name, reason
        )
        AuditLog.log(self.session, requester.id, "edit_member", message, on_group_id=self.id)
        self.session.commit()

    @flush_transaction
    def add_member(
        self,
        requester: User,
        user_or_group: Union[User, Group],
        reason: str,
        status: str = "pending",
        expiration: Optional[datetime] = None,
        role: str = "member",
    ) -> Request:
        """Add a member (User or Group) to this group.

        Args:
            requester: A User object of the person requesting the addition
            user_or_group: A User/Group object of the member
            reason: A comment on why this member should exist
            status: pending/actioned, whether the request needs approval
                    or should be immediate
            expiration: datetime object when membership should expire.
            role: member/manager/owner/np-owner of the Group.
        """
        logging.debug("Adding member (%s) to %s", user_or_group.name, self.groupname)

        return persist_group_member_changes(
            session=self.session,
            group=self,
            requester=requester,
            member=user_or_group,
            status=status,
            reason=reason,
            create_edge=True,
            role=role,
            expiration=expiration,
            active=True,
        )

    def my_permissions(self) -> List[Any]:
        """All permissions granted to a group.

        NOTE: Disabled permissions are not returned
        """
        permissions = (
            self.session.query(
                Permission.id,
                Permission.name,
                label("mapping_id", PermissionMap.id),
                PermissionMap.argument,
                PermissionMap.granted_on,
            )
            .filter(
                Permission.enabled == True,
                PermissionMap.permission_id == Permission.id,
                PermissionMap.group_id == self.id,
            )
            .all()
        )

        return permissions

    def my_users(self) -> List[Any]:
        now = datetime.utcnow()
        users = (
            self.session.query(label("name", User.username), label("role", GroupEdge._role))
            .filter(
                GroupEdge.group_id == self.id,
                GroupEdge.member_pk == User.id,
                GroupEdge.member_type == 0,
                GroupEdge.active == True,
                self.enabled == True,
                User.enabled == True,
                User.is_service_account == False,
                or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
            )
            .all()
        )

        return users

    def my_approver_users(self) -> List[User]:
        """Returns a list of all users in this group that are approvers."""
        return [user for user in self.my_users() if user.role in APPROVER_ROLE_INDICES]

    def my_log_entries(self) -> List[Any]:
        return AuditLog.get_entries(self.session, on_group_id=self.id, limit=20)

    def my_owners_as_strings(self) -> List[str]:
        """Returns a list of usernames."""
        return list(self.my_owners().keys())

    def my_owners(self) -> OrderedDict[str, User]:
        """Returns a dictionary from username to records."""
        od: OrderedDict[str, User] = OrderedDict()
        for (member_type, name), member in self.my_members().items():
            if member_type == "User" and member.role in OWNER_ROLE_INDICES:
                od[name] = member
        return od

    def my_members(self) -> Mapping[Tuple[str, str], Any]:
        """Returns a dictionary from ("User"|"Group", "name") tuples to records."""

        parent = aliased(Group)
        group_member = aliased(Group)
        user_member = aliased(User)

        now = datetime.utcnow()

        users = (
            self.session.query(
                label("id", user_member.id),
                label("type", literal("User")),
                label("name", user_member.username),
                label("role", GroupEdge._role),
                label("edge_id", GroupEdge.id),
                label("expiration", GroupEdge.expiration),
            )
            .filter(
                parent.id == self.id,
                parent.id == GroupEdge.group_id,
                user_member.id == GroupEdge.member_pk,
                GroupEdge.active == True,
                parent.enabled == True,
                user_member.enabled == True,
                or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
                GroupEdge.member_type == 0,
            )
            .order_by(desc("role"), "name")
        )

        groups = (
            self.session.query(
                label("id", group_member.id),
                label("type", literal("Group")),
                label("name", group_member.groupname),
                label("role", GroupEdge._role),
                label("edge_id", GroupEdge.id),
                label("expiration", GroupEdge.expiration),
            )
            .filter(
                parent.id == self.id,
                parent.id == GroupEdge.group_id,
                group_member.id == GroupEdge.member_pk,
                GroupEdge.active == True,
                parent.enabled == True,
                group_member.enabled == True,
                or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
                GroupEdge.member_type == 1,
            )
            .order_by(desc("role"), "name")
        )

        return OrderedDict(((r.type, r.name), r) for r in itertools.chain(users, groups))

    def my_groups(self) -> List[Any]:
        """Return the groups to which this group currently belongs."""
        now = datetime.utcnow()
        groups = (
            self.session.query(
                label("name", Group.groupname),
                label("type", literal("Group")),
                label("role", GroupEdge._role),
            )
            .filter(
                GroupEdge.group_id == Group.id,
                GroupEdge.member_pk == self.id,
                GroupEdge.member_type == 1,
                GroupEdge.active == True,
                self.enabled == True,
                Group.enabled == True,
                or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
            )
            .all()
        )
        return groups

    def my_expiring_groups(self) -> List[Any]:
        """Return the groups to which this group currently belongs but with an
        expiration date.
        """
        now = datetime.utcnow()
        groups = (
            self.session.query(
                label("name", Group.groupname), label("expiration", GroupEdge.expiration)
            )
            .filter(
                GroupEdge.group_id == Group.id,
                GroupEdge.member_pk == self.id,
                GroupEdge.member_type == 1,
                GroupEdge.active == True,
                self.enabled == True,
                Group.enabled == True,
                GroupEdge.expiration > now,
            )
            .all()
        )
        return groups

    def enable(self) -> None:
        self.enabled = True
        Counter.incr(self.session, "updates")

    def disable(self) -> None:
        self.enabled = False
        Counter.incr(self.session, "updates")

    @staticmethod
    def get(
        session: Session, pk: Optional[int] = None, name: Optional[str] = None
    ) -> Optional[Group]:
        if pk is not None:
            return session.query(Group).filter_by(id=pk).scalar()
        if name is not None:
            return session.query(Group).filter_by(groupname=name).scalar()
        return None

    def add(self, session: Session) -> Group:
        super().add(session)
        Counter.incr(session, "updates")
        return self

    def __repr__(self) -> str:
        return "<%s: id=%s groupname=%s>" % (type(self).__name__, self.id, self.groupname)
