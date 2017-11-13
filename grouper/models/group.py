from collections import OrderedDict
from datetime import datetime
import logging
from typing import List  # noqa

from sqlalchemy import Boolean, Column, desc, Enum, Integer, Interval, or_, String, Text, union_all
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.orm.util import aliased
from sqlalchemy.sql import label, literal

from grouper.constants import MAX_NAME_LENGTH
from grouper.group_member import persist_group_member_changes
from grouper.models.audit import Audit
from grouper.models.audit_log import AuditLog
from grouper.models.base.constants import OBJ_TYPES_IDX
from grouper.models.base.model_base import Model
from grouper.models.base.session import flush_transaction
from grouper.models.comment import Comment, CommentObjectMixin
from grouper.models.counter import Counter
from grouper.models.group_edge import APPROVER_ROLE_INDICES, GroupEdge, OWNER_ROLE_INDICES
from grouper.models.permission import Permission
from grouper.models.permission_map import PermissionMap
from grouper.models.request import Request
from grouper.models.request_status_change import RequestStatusChange
from grouper.models.user import User

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
    email_address = Column(String(length=MAX_NAME_LENGTH), unique=False, nullable=True,)
    description = Column(Text)
    canjoin = Column(Enum(*GROUP_JOIN_CHOICES), default="canask")
    enabled = Column(Boolean, default=True, nullable=False)
    # The default amount of time new users have before their membership in the group is expired
    # NOTE: This only applies to users who join a group via a request in the front end. It does
    # not apply to users who are added to a group by an approver
    auto_expire = Column(Interval)

    audit_id = Column(Integer, nullable=True)
    audit = relationship("Audit", foreign_keys=[audit_id],
                         primaryjoin=lambda: Audit.id == Group.audit_id)

    @hybrid_property
    def name(self):
        return self.groupname

    @property
    def type(self):
        return "Group"

    @flush_transaction
    def revoke_member(self, requester, user_or_group, reason):
        """ Revoke a member (User or Group) from this group.

            Arguments:
                requester: A User object of the person requesting the addition
                user_or_group: A User/Group object of the member
                reason: A comment on why this member should exist
        """
        logging.debug(
            "Revoking member (%s) from %s", user_or_group.name, self.groupname
        )

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
            active=False
        )

    @flush_transaction
    def edit_member(self, requester, user_or_group, reason, **kwargs):
        """ Edit an existing member (User or Group) of a group.

            This takes the same parameters as add_member, except that we do not allow you to set
            a status: this only works on existing members.

            Any option that is not passed is not updated, and instead, the existing value for this
            user is kept.
        """
        logging.debug(
            "Editing member (%s) in %s", user_or_group.name, self.groupname
        )

        persist_group_member_changes(
            session=self.session,
            group=self,
            requester=requester,
            member=user_or_group,
            status="actioned",
            reason=reason,
            **kwargs
        )

        member_type = user_or_group.member_type

        message = "Edit member {} {}: {}".format(
            OBJ_TYPES_IDX[member_type].lower(), user_or_group.name, reason)
        AuditLog.log(self.session, requester.id, 'edit_member',
                     message, on_group_id=self.id)

    @flush_transaction
    def add_member(self, requester, user_or_group, reason, status="pending",
                   expiration=None, role="member"):
        """ Add a member (User or Group) to this group.

            Arguments:
                requester: A User object of the person requesting the addition
                user_or_group: A User/Group object of the member
                reason: A comment on why this member should exist
                status: pending/actioned, whether the request needs approval
                        or should be immediate
                expiration: datetime object when membership should expire.
                role: member/manager/owner/np-owner of the Group.
        """
        logging.debug(
            "Adding member (%s) to %s", user_or_group.name, self.groupname
        )

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
            active=True
        )

    def my_permissions(self):

        permissions = self.session.query(
            Permission.id,
            Permission.name,
            label("mapping_id", PermissionMap.id),
            PermissionMap.argument,
            PermissionMap.granted_on,
        ).filter(
            PermissionMap.permission_id == Permission.id,
            PermissionMap.group_id == self.id,
        ).all()

        return permissions

    def my_users(self):

        now = datetime.utcnow()
        users = self.session.query(
            label("name", User.username),
            label("role", GroupEdge._role)
        ).filter(
            GroupEdge.group_id == self.id,
            GroupEdge.member_pk == User.id,
            GroupEdge.member_type == 0,
            GroupEdge.active == True,
            self.enabled == True,
            User.enabled == True,
            or_(
                GroupEdge.expiration > now,
                GroupEdge.expiration == None
            )
        ).all()

        return users

    def my_approver_users(self):
        # type: () -> List[User]
        """Returns a list of all users in this group that are approvers.

        Returns:
            A list of all User objects that are approvers for this group.
        """

        return [user for user in self.my_users() if user.role in APPROVER_ROLE_INDICES]

    def my_log_entries(self):

        return AuditLog.get_entries(self.session, on_group_id=self.id, limit=20)

    def my_owners_as_strings(self):
        """Returns a list of usernames."""
        return self.my_owners().keys()

    def my_owners(self):
        """Returns a dictionary from username to records."""
        od = OrderedDict()
        for (member_type, name), member in self.my_members().iteritems():
            if member_type == "User" and member.role in OWNER_ROLE_INDICES:
                od[name] = member
        return od

    def my_members(self):
        """Returns a dictionary from ("User"|"Group", "name") tuples to records."""

        parent = aliased(Group)
        group_member = aliased(Group)
        user_member = aliased(User)

        now = datetime.utcnow()

        users = self.session.query(
            label("id", user_member.id),
            label("type", literal("User")),
            label("name", user_member.username),
            label("role", GroupEdge._role),
            label("edge_id", GroupEdge.id),
            label("expiration", GroupEdge.expiration)
        ).filter(
            parent.id == self.id,
            parent.id == GroupEdge.group_id,
            user_member.id == GroupEdge.member_pk,
            GroupEdge.active == True,
            parent.enabled == True,
            user_member.enabled == True,
            or_(
                GroupEdge.expiration > now,
                GroupEdge.expiration == None
            ),
            GroupEdge.member_type == 0
        ).group_by(
            "type", "name"
        ).subquery()

        groups = self.session.query(
            label("id", group_member.id),
            label("type", literal("Group")),
            label("name", group_member.groupname),
            label("role", GroupEdge._role),
            label("edge_id", GroupEdge.id),
            label("expiration", GroupEdge.expiration)
        ).filter(
            parent.id == self.id,
            parent.id == GroupEdge.group_id,
            group_member.id == GroupEdge.member_pk,
            GroupEdge.active == True,
            parent.enabled == True,
            group_member.enabled == True,
            or_(
                GroupEdge.expiration > now,
                GroupEdge.expiration == None
            ),
            GroupEdge.member_type == 1
        ).subquery()

        query = self.session.query(
            "id", "type", "name", "role", "edge_id", "expiration"
        ).select_entity_from(
            union_all(users.select(), groups.select())
        ).order_by(
            desc("role"), desc("type")
        )

        return OrderedDict(
            ((record.type, record.name), record)
            for record in query.all()
        )

    def my_groups(self):
        """Return the groups to which this group currently belongs."""
        now = datetime.utcnow()
        groups = self.session.query(
            label("name", Group.groupname),
            label("type", literal("Group")),
            label("role", GroupEdge._role)
        ).filter(
            GroupEdge.group_id == Group.id,
            GroupEdge.member_pk == self.id,
            GroupEdge.member_type == 1,
            GroupEdge.active == True,
            self.enabled == True,
            Group.enabled == True,
            or_(
                GroupEdge.expiration > now,
                GroupEdge.expiration == None
            )
        ).all()
        return groups

    def my_expiring_groups(self):
        """Return the groups to which this group currently belongs but with an
        expiration date.
        """
        now = datetime.utcnow()
        groups = self.session.query(
            label("name", Group.groupname),
            label("expiration", GroupEdge.expiration)
        ).filter(
            GroupEdge.group_id == Group.id,
            GroupEdge.member_pk == self.id,
            GroupEdge.member_type == 1,
            GroupEdge.active == True,
            self.enabled == True,
            Group.enabled == True,
            GroupEdge.expiration > now
        ).all()
        return groups

    def my_requests(self, status=None, user=None):

        members = self.session.query(
            label("type", literal(1)),
            label("id", Group.id),
            label("name", Group.groupname)
        ).union(self.session.query(
            label("type", literal(0)),
            label("id", User.id),
            label("name", User.username)
        )).subquery()

        requests = self.session.query(
            Request.id,
            Request.requested_at,
            GroupEdge.expiration,
            label("role", GroupEdge._role),
            Request.status,
            label("requester", User.username),
            label("type", members.c.type),
            label("requesting", members.c.name),
            label("reason", Comment.comment),
        ).filter(
            Request.on_behalf_obj_pk == members.c.id,
            Request.on_behalf_obj_type == members.c.type,
            Request.requesting_id == self.id,
            Request.requester_id == User.id,
            Request.id == RequestStatusChange.request_id,
            RequestStatusChange.from_status == None,
            GroupEdge.id == Request.edge_id,
            Comment.obj_type == 3,
            Comment.obj_pk == RequestStatusChange.id
        )

        if status:
            requests = requests.filter(
                Request.status == status
            )

        if user:
            requests = requests.filter(
                Request.on_behalf_obj_pk == user.id,
                Request.on_behalf_obj_type == 0
            )

        return requests

    def enable(self):
        self.enabled = True
        Counter.incr(self.session, "updates")

    def disable(self):
        self.enabled = False
        Counter.incr(self.session, "updates")

    @staticmethod
    def get(session, pk=None, name=None):
        if pk is not None:
            return session.query(Group).filter_by(id=pk).scalar()
        if name is not None:
            return session.query(Group).filter_by(groupname=name).scalar()
        return None

    def add(self, session):
        super(Group, self).add(session)
        Counter.incr(session, "updates")
        return self

    def __repr__(self):
        return "<%s: id=%s groupname=%s>" % (
            type(self).__name__, self.id, self.groupname)
