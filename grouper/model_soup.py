################################################################################
#                                                                              #
# THIS MODULE IS DEPRECIATED. PLEASE DON'T ADD TO THE SPAGHETTI HERE IF YOU    #
# CAN AVOID IT.                                                                #
#                                                                              #
################################################################################
from collections import OrderedDict
from datetime import datetime, timedelta
import json
import logging

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Index,
    Integer, Interval, SmallInteger, String, Text
)
from sqlalchemy import desc, or_, union_all
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import aliased
from sqlalchemy.orm import relationship
from sqlalchemy.sql import label, literal

from grouper.models.audit_log import AuditLog
from grouper.models.base.constants import OBJ_TYPES_IDX, REQUEST_STATUS_CHOICES
from grouper.models.base.model_base import Model
from grouper.models.base.session import flush_transaction
from grouper.models.comment import Comment, CommentObjectMixin
from grouper.models.counter import Counter
from grouper.models.permission import Permission
from grouper.models.permission_map import PermissionMap
from grouper.models.user import User
from .constants import ILLEGAL_NAME_CHARACTER, MAX_NAME_LENGTH
from .email_util import send_async_email
from .settings import settings


GROUP_JOIN_CHOICES = {
    # Anyone can join with automatic approval
    "canjoin": "actioned",
    # Anyone can ask to join this group
    "canask": "pending",
    # Only those invited may join (should never be a valid status because no
    # join request should be generated for such groups!)
    "nobody": "<integrityerror>",
}

AUDIT_STATUS_CHOICES = {"pending", "approved", "remove"}

# Note: the order of the GROUP_EDGE_ROLES tuple matters! New roles must be
# appended!  When adding a new role, be sure to update the regression test.
GROUP_EDGE_ROLES = (
    "member",    # Belongs to the group. Nothing more.
    "manager",   # Make changes to the group / Approve requests.
    "owner",     # Same as manager plus enable/disable group and make Users owner.
    "np-owner",  # Same as owner but don't inherit permissions.
)
OWNER_ROLE_INDICES = set([GROUP_EDGE_ROLES.index("owner"), GROUP_EDGE_ROLES.index("np-owner")])
APPROVER_ROLE_INDICIES = set([GROUP_EDGE_ROLES.index("owner"), GROUP_EDGE_ROLES.index("np-owner"),
        GROUP_EDGE_ROLES.index("manager")])  # TODO: Fix spelling


def build_changes(edge, **updates):
    changes = {}
    for key, value in updates.items():
        if key not in ("role", "expiration", "active"):
            continue
        if getattr(edge, key) != value:
            if key == "expiration":
                changes[key] = value.strftime("%m/%d/%Y") if value else ""
            else:
                changes[key] = value
    return json.dumps(changes)


class MemberNotFound(Exception):
    """This exception is raised when trying to perform a group operation on an account that is
       not a member of the group."""
    pass


class InvalidRoleForMember(Exception):
    """This exception is raised when trying to set the role for a member of a group, but that
    member is not permitted to hold that role in the group"""
    pass


class Group(Model, CommentObjectMixin):

    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    groupname = Column(String(length=MAX_NAME_LENGTH), unique=True, nullable=False)
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
        now = datetime.utcnow()

        logging.debug(
            "Revoking member (%s) from %s", user_or_group.name, self.groupname
        )

        # Create the edge even if it doesn't exist so that we can explicitly
        # disable it.
        edge, new = GroupEdge.get_or_create(
            self.session,
            group_id=self.id,
            member_type=user_or_group.member_type,
            member_pk=user_or_group.id,
        )
        self.session.flush()

        request = Request(
            requester_id=requester.id,
            requesting_id=self.id,
            on_behalf_obj_type=user_or_group.member_type,
            on_behalf_obj_pk=user_or_group.id,
            requested_at=now,
            edge_id=edge.id,
            status="actioned",
            changes=build_changes(
                edge, role="member", expiration=None, active=False
            )
        ).add(self.session)
        self.session.flush()

        request_status_change = RequestStatusChange(
            request=request,
            user_id=requester.id,
            to_status="actioned",
            change_at=now
        ).add(self.session)
        self.session.flush()

        Comment(
            obj_type=OBJ_TYPES_IDX.index("RequestStatusChange"),
            obj_pk=request_status_change.id,
            user_id=requester.id,
            comment=reason,
            created_on=now
        ).add(self.session)

        edge.apply_changes(request)
        self.session.flush()

        Counter.incr(self.session, "updates")

    @flush_transaction
    def edit_member(self, requester, user_or_group, reason, **kwargs):
        """ Edit an existing member (User or Group) of a group.

            This takes the same parameters as add_member, except that we do not allow you to set
            a status: this only works on existing members.

            Any option that is not passed is not updated, and instead, the existing value for this
            user is kept.
        """
        now = datetime.utcnow()
        member_type = user_or_group.member_type

        if member_type == 1 and "role" in kwargs and kwargs["role"] != "member":
            raise InvalidRoleForMember("Groups can only have the role of 'member'")

        logging.debug(
            "Editing member (%s) in %s", user_or_group.name, self.groupname
        )

        edge = GroupEdge.get(
            self.session,
            group_id=self.id,
            member_type=member_type,
            member_pk=user_or_group.id,
        )
        self.session.flush()

        if not edge:
            raise MemberNotFound()

        request = Request(
            requester_id=requester.id,
            requesting_id=self.id,
            on_behalf_obj_type=member_type,
            on_behalf_obj_pk=user_or_group.id,
            requested_at=now,
            edge_id=edge.id,
            status="actioned",
            changes=build_changes(
                edge, **kwargs
            ),
        ).add(self.session)
        self.session.flush()

        request_status_change = RequestStatusChange(
            request=request,
            user_id=requester.id,
            to_status="actioned",
            change_at=now,
        ).add(self.session)
        self.session.flush()

        Comment(
            obj_type=OBJ_TYPES_IDX.index("RequestStatusChange"),
            obj_pk=request_status_change.id,
            user_id=requester.id,
            comment=reason,
            created_on=now,
        ).add(self.session)

        edge.apply_changes(request)
        self.session.flush()

        message = "Edit member {} {}: {}".format(
            OBJ_TYPES_IDX[member_type].lower(), user_or_group.name, reason)
        AuditLog.log(self.session, requester.id, 'edit_member',
                     message, on_group_id=self.id)

        Counter.incr(self.session, "updates")

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
        now = datetime.utcnow()
        member_type = user_or_group.member_type

        if member_type == 1 and role != "member":
            raise InvalidRoleForMember("Groups can only have the role of 'member'")

        logging.debug(
            "Adding member (%s) to %s", user_or_group.name, self.groupname
        )

        edge, new = GroupEdge.get_or_create(
            self.session,
            group_id=self.id,
            member_type=member_type,
            member_pk=user_or_group.id,
        )

        # TODO(herb): this means all requests by this user to this group will
        # have the same role. we should probably record the role specifically
        # on the request and use that as the source on the UI
        edge._role = GROUP_EDGE_ROLES.index(role)

        self.session.flush()

        request = Request(
            requester_id=requester.id,
            requesting_id=self.id,
            on_behalf_obj_type=member_type,
            on_behalf_obj_pk=user_or_group.id,
            requested_at=now,
            edge_id=edge.id,
            status=status,
            changes=build_changes(
                edge, role=role, expiration=expiration, active=True
            )
        ).add(self.session)
        self.session.flush()

        request_status_change = RequestStatusChange(
            request=request,
            user_id=requester.id,
            to_status=status,
            change_at=now
        ).add(self.session)
        self.session.flush()

        Comment(
            obj_type=3,
            obj_pk=request_status_change.id,
            user_id=requester.id,
            comment=reason,
            created_on=now
        ).add(self.session)

        if status == "actioned":
            edge.apply_changes(request)
            self.session.flush()

        Counter.incr(self.session, "updates")

        return request.id

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

        return [user for user in self.my_users() if user.role in APPROVER_ROLE_INDICIES]

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


class AuditMember(Model):
    """An AuditMember is a single instantiation of a user in an audit

    Tracks the status of the member within the audit. I.e., have they been reviewed, should they
    be removed, etc.
    """

    __tablename__ = "audit_members"

    id = Column(Integer, primary_key=True)

    audit_id = Column(Integer, ForeignKey("audits.id"), nullable=False)
    audit = relationship("Audit", backref="members", foreign_keys=[audit_id])

    edge_id = Column(Integer, ForeignKey("group_edges.id"), nullable=False)
    edge = relationship("GroupEdge", backref="audits", foreign_keys=[edge_id])

    status = Column(Enum(*AUDIT_STATUS_CHOICES), default="pending", nullable=False)

    @hybrid_property
    def member(self):
        if self.edge.member_type == 0:  # User
            return User.get(self.session, pk=self.edge.member_pk)
        elif self.edge.member_type == 1:  # Group
            return Group.get(self.session, pk=self.edge.member_pk)
        raise Exception("invalid member_type in AuditMember!")


class Audit(Model):
    """An Audit is applied to a group for a particular audit period

    This contains all of the state of a given audit including each of the members who were
    present in the group at the beginning of the audit period.
    """

    __tablename__ = "audits"

    id = Column(Integer, primary_key=True)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group = relationship("Group", foreign_keys=[group_id])

    # If this audit is complete and when it started/ended
    complete = Column(Boolean, default=False, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ends_at = Column(DateTime, nullable=False)

    # Tracks the last time we emailed the responsible parties of this audit
    last_reminder_at = Column(DateTime, nullable=True)

    def my_members(self):
        """Return all members of this audit

        Only currently valid members (haven't since left the group and haven't joined since the
        audit started).

        Returns:
            list(AuditMember): the members of the audit.
        """

        # Get all members of the audit. Note that this list might change since people can
        # join or leave the group.
        auditmembers = self.session.query(AuditMember).filter(
            AuditMember.audit_id == self.id
        ).all()

        auditmember_by_edge_id = {am.edge_id: am for am in auditmembers}

        # Now get current members of the group. If someone has left the group, we don't include
        # them in the audit anymore. If someone new joins (or rejoins) then we also don't want
        # to audit them since they had to get approved into the group.
        auditmember_name_pairs = []
        for member in self.group.my_members().values():
            if member.edge_id in auditmember_by_edge_id:
                auditmember_name_pairs.append((member.name, auditmember_by_edge_id[member.edge_id]))

        # Sort by name and return members
        return [auditmember for _, auditmember in sorted(auditmember_name_pairs)]

    @property
    def completable(self):
        """Whether or not this audit is completable

        This is defined as "when all members have been assigned a non-pending status". I.e., at
        that point, we can hit the Complete button which will perform any actions necessary to
        the membership.

        Returns:
            bool: Whether or not this audit can be marked as completed.
        """
        return all([member.status != "pending" for member in self.my_members()])


class Request(Model, CommentObjectMixin):

    __tablename__ = "requests"

    id = Column(Integer, primary_key=True)

    # The User that made the request.
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requester = relationship(
        User, backref="requests", foreign_keys=[requester_id]
    )

    # The Group the requester is requesting access to.
    requesting_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    requesting = relationship(
        Group, backref="requests", foreign_keys=[requesting_id]
    )

    # The User/Group which will become a member of the requested resource.
    on_behalf_obj_type = Column(Integer, nullable=False)
    on_behalf_obj_pk = Column(Integer, nullable=False)

    edge_id = Column(Integer, ForeignKey("group_edges.id"), nullable=False)
    edge = relationship("GroupEdge", backref="requests")

    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    status = Column(
        Enum(*REQUEST_STATUS_CHOICES), default="pending", nullable=False
    )

    changes = Column(Text, nullable=False)

    def get_on_behalf(self):
        obj_type = OBJ_TYPES_IDX[self.on_behalf_obj_type]

        if obj_type == "User":
            obj = User
        elif obj_type == "Group":
            obj = Group

        return self.session.query(obj).filter_by(id=self.on_behalf_obj_pk).scalar()

    def my_status_updates(self):

        requests = self.session.query(
            Request.id,
            RequestStatusChange.change_at,
            RequestStatusChange.from_status,
            RequestStatusChange.to_status,
            label("changed_by", User.username),
            label("reason", Comment.comment)
        ).filter(
            RequestStatusChange.user_id == User.id,
            Request.id == RequestStatusChange.request_id,
            Comment.obj_type == 3,
            Comment.obj_pk == RequestStatusChange.id,
            Request.id == self.id
        )

        return requests

    @flush_transaction
    def update_status(self, requester, status, reason):
        now = datetime.utcnow()
        current_status = self.status
        self.status = status

        request_status_change = RequestStatusChange(
            request=self,
            user_id=requester.id,
            from_status=current_status,
            to_status=status,
            change_at=now
        ).add(self.session)
        self.session.flush()

        Comment(
            obj_type=OBJ_TYPES_IDX.index("RequestStatusChange"),
            obj_pk=request_status_change.id,
            user_id=requester.id,
            comment=reason,
            created_on=now
        ).add(self.session)

        if status == "actioned":
            edge = self.session.query(GroupEdge).filter_by(
                id=self.edge_id
            ).one()
            edge.apply_changes(self)

        Counter.incr(self.session, "updates")


class RequestStatusChange(Model, CommentObjectMixin):

    __tablename__ = "request_status_changes"

    id = Column(Integer, primary_key=True)

    request_id = Column(Integer, ForeignKey("requests.id"))
    request = relationship(Request)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship(User, foreign_keys=[user_id])

    from_status = Column(Enum(*REQUEST_STATUS_CHOICES))
    to_status = Column(Enum(*REQUEST_STATUS_CHOICES), nullable=False)

    change_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class GroupEdge(Model):

    __tablename__ = "group_edges"
    __table_args__ = (
        Index(
            "group_member_idx",
            "group_id", "member_type", "member_pk",
            unique=True
        ),
    )

    id = Column(Integer, primary_key=True)

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group = relationship(Group, backref="edges", foreign_keys=[group_id])

    member_type = Column(Integer, nullable=False)
    member_pk = Column(Integer, nullable=False)

    expiration = Column(DateTime)
    active = Column(Boolean, default=False, nullable=False)
    _role = Column(SmallInteger, default=0, nullable=False)

    @hybrid_property
    def role(self):
        return GROUP_EDGE_ROLES[self._role]

    @role.setter
    def role(self, role):
        prev_role = self._role
        self._role = GROUP_EDGE_ROLES.index(role)

        # Groups should always "member".
        if not (OBJ_TYPES_IDX[self.member_type] == "User"):
            return

        # If ownership status is unchanged, no notices need to be adjusted.
        if (self._role in OWNER_ROLE_INDICES) == (prev_role in OWNER_ROLE_INDICES):
            return

        recipient = User.get(self.session, pk=self.member_pk).username
        expiring_supergroups = self.group.my_expiring_groups()
        member_name = self.group.name

        if role in ["owner", "np-owner"]:
            # We're creating a new owner, who should find out when this group
            # they now own loses its membership in larger groups.
            for supergroup_name, expiration in expiring_supergroups:
                AsyncNotification.add_expiration(self.session,
                                                 expiration,
                                                 group_name=supergroup_name,
                                                 member_name=member_name,
                                                 recipients=[recipient],
                                                 member_is_user=False)
        else:
            # We're removing an owner, who should no longer find out when this
            # group they no longer own loses its membership in larger groups.
            for supergroup_name, _ in expiring_supergroups:
                AsyncNotification.cancel_expiration(self.session,
                                                    group_name=supergroup_name,
                                                    member_name=member_name,
                                                    recipients=[recipient])

    def apply_changes_dict(self, changes):
        for key, value in changes.items():
            if key == 'expiration':
                group_name = self.group.name
                if OBJ_TYPES_IDX[self.member_type] == "User":
                    # If affected member is a user, plan to notify that user.
                    user = User.get(self.session, pk=self.member_pk)
                    member_name = user.username
                    recipients = [member_name]
                    member_is_user = True
                else:
                    # Otherwise, affected member is a group, notify its owners.
                    subgroup = Group.get(self.session, pk=self.member_pk)
                    member_name = subgroup.groupname
                    recipients = subgroup.my_owners_as_strings()
                    member_is_user = False
                if getattr(self, key, None) is not None:
                    # Check for and remove pending expiration notification.
                    AsyncNotification.cancel_expiration(self.session,
                                                        group_name,
                                                        member_name)
                if value:
                    expiration = datetime.strptime(value, "%m/%d/%Y")
                    setattr(self, key, expiration)
                    # Avoid sending notifications for expired edges.
                    if expiration > datetime.utcnow():
                        AsyncNotification.add_expiration(self.session,
                                                         expiration,
                                                         group_name,
                                                         member_name,
                                                         recipients=recipients,
                                                         member_is_user=member_is_user)
                else:
                    setattr(self, key, None)
            else:
                setattr(self, key, value)

    def apply_changes(self, request):
        # TODO(tyleromeara): Move deserialization elsewhere
        changes = json.loads(request.changes)
        return self.apply_changes_dict(changes)

    def __repr__(self):
        return "%s(group_id=%s, member_type=%s, member_pk=%s)" % (
            type(self).__name__, self.group_id,
            OBJ_TYPES_IDX[self.member_type], self.member_pk
        )


class AsyncNotification(Model):
    """Represent a notification tracking/sending mechanism"""

    __tablename__ = "async_notifications"

    id = Column(Integer, primary_key=True)
    key = Column(String(length=MAX_NAME_LENGTH))

    email = Column(String(length=MAX_NAME_LENGTH), nullable=False)
    subject = Column(String(length=256), nullable=False)
    body = Column(Text, nullable=False)
    send_after = Column(DateTime, nullable=False)
    sent = Column(Boolean, default=False, nullable=False)

    @staticmethod
    def _get_unsent_expirations(session, now_ts):
        """Get upcoming group membership expiration notifications as a list of (group_name,
        member_name, email address) tuples.
        """
        tuples = []
        emails = session.query(AsyncNotification).filter(
            AsyncNotification.key.like("EXPIRATION%"),
            AsyncNotification.sent == False,
            AsyncNotification.send_after < now_ts,
        ).all()
        for email in emails:
            group_name, member_name = AsyncNotification._expiration_key_data(email.key)
            user = email.email
            tuples.append((group_name, member_name, user))
        return tuples

    @staticmethod
    def _expiration_key_data(key):
        expiration_token, group_name, member_name = key.split(ILLEGAL_NAME_CHARACTER)
        assert expiration_token == 'EXPIRATION'
        return group_name, member_name

    @staticmethod
    def _expiration_key(group_name, member_name):
        async_key = ILLEGAL_NAME_CHARACTER.join(['EXPIRATION', group_name, member_name])
        return async_key

    @staticmethod
    def add_expiration(session, expiration, group_name, member_name, recipients, member_is_user):
        async_key = AsyncNotification._expiration_key(group_name, member_name)
        send_after = expiration - timedelta(settings.expiration_notice_days)
        email_context = {
                'expiration': expiration,
                'group_name': group_name,
                'member_name': member_name,
                'member_is_user': member_is_user,
                }
        from grouper.fe.settings import settings as fe_settings
        send_async_email(
                session=session,
                recipients=recipients,
                subject="expiration warning for membership in group '{}'".format(group_name),
                template='expiration_warning',
                settings=fe_settings,
                context=email_context,
                send_after=send_after,
                async_key=async_key)

    @staticmethod
    def cancel_expiration(session, group_name, member_name, recipients=None):
        async_key = AsyncNotification._expiration_key(group_name, member_name)
        opt_arg = []
        if recipients is not None:
            exprs = [AsyncNotification.email == recipient for recipient in recipients]
            opt_arg.append(or_(*exprs))
        session.query(AsyncNotification).filter(
            AsyncNotification.key == async_key,
            AsyncNotification.sent == False,
            *opt_arg
        ).delete()
        session.commit()
