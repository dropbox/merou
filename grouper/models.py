
from collections import OrderedDict
from datetime import datetime
import functools
import json
import logging

from sqlalchemy import create_engine
from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    ForeignKey, Enum, DateTime, SmallInteger, Index
)
from sqlalchemy import or_, union_all, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, object_session
from sqlalchemy.orm import aliased
from sqlalchemy.orm import sessionmaker, Session as _Session
from sqlalchemy.sql import func, label, literal

from .capabilities import Capabilities


OBJ_TYPES_IDX = ("User", "Group", "Request", "RequestStatusChange")
OBJ_TYPES = {obj_type: idx for idx, obj_type in enumerate(OBJ_TYPES_IDX)}

GROUP_JOIN_CHOICES = {
    "canjoin": "actioned",  # Anyone can join with automatic approval
    "canask": "pending",   # Anyone can ask to join this group
}

REQUEST_STATUS_CHOICES = {
    # Request has been made and awaiting action.
    "pending": set(["actioned", "cancelled"]),
    "actioned": set([]),
    "cancelled": set([]),
}
GROUP_EDGE_ROLES = (
    "member",   # Belongs to the group. Nothing more.
    "manager",  # Make changes to the group / Approve requests.
    "owner",    # Same as manager plus enable/disable group and make Users owner.
)


class Session(_Session):
    """ Custom session meant to utilize add on the model.

        This Session overrides the add/add_all methods to prevent them
        from being used. This is to for using the add methods on the
        models themselves where overriding is available.
    """

    _add = _Session.add
    _add_all = _Session.add_all

    def add(self, *args, **kwargs):
        raise NotImplementedError("Use add method on models instead.")

    def add_all(self, *args, **kwargs):
        raise NotImplementedError("Use add method on models instead.")


Session = sessionmaker(class_=Session)


class Model(object):
    """ Custom model mixin with helper methods. """

    @property
    def session(self):
        return object_session(self)

    @property
    def member_type(self):
        obj_name = type(self).__name__
        if obj_name not in OBJ_TYPES:
            raise ValueError()  # TODO(gary) fill out error
        return OBJ_TYPES[obj_name]

    @classmethod
    def get_or_create(cls, session, **kwargs):
        instance = session.query(cls).filter_by(**kwargs).scalar()
        if instance:
            return instance, False

        instance = cls(**kwargs)
        instance.add(session)

        return instance, True

    def add(self, session):
        session._add(self)
        return self


Model = declarative_base(cls=Model)


def get_db_engine(url):
    return create_engine(url, pool_recycle=300)


def flush_transaction(method):
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        dryrun = kwargs.pop("dryrun", False)
        try:
            ret = method(self, *args, **kwargs)
            if dryrun:
                self.session.rollback()
            else:
                self.session.flush()
        except Exception:
            logging.exception("Transaction Failed. Rolling back.")
            if self.session is not None:
                self.session.rollback()
            raise
        return ret
    return wrapper


class User(Model):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(length=32), unique=True, nullable=False)
    capabilities = Column(Integer, default=0, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    @hybrid_property
    def name(self):
        return self.username

    def __repr__(self):
        return "<%s: id=%s username=%s>" % (
            type(self).__name__, self.id, self.username)

    @staticmethod
    def get(session, pk=None, name=None):
        if pk is not None:
            return session.query(User).filter_by(id=pk).scalar()
        if name is not None:
            return session.query(User).filter_by(username=name).scalar()
        return None

    def enable(self):
        self.enabled = True
        Counter.incr(self.session, "updates")

    def disable(self, requester):
        for group in self.my_groups():
            group_obj = self.session.query(Group).filter_by(
                groupname=group.name
            ).scalar()
            if group_obj:
                group_obj.revoke_member(
                    requester, self, "Account has been disabled."
                )

        self.enabled = False
        Counter.incr(self.session, "updates")

    def add(self, session):
        super(User, self).add(session)
        Counter.incr(session, "updates")
        return self

    @property
    def user_admin(self):
        return Capabilities(self.capabilities).has("user_admin")

    @property
    def group_admin(self):
        return Capabilities(self.capabilities).has("group_admin")

    def is_member(self, members):
        return ("User", self.name) in members

    def my_role(self, members):
        if self.group_admin:
            return "owner"
        member = members.get(("User", self.name))
        if not member:
            return None
        return GROUP_EDGE_ROLES[member.role]

    def pending_requests(self):
        """ Returns all pending requests actionable by this user. """
        #TODO(gary) Do.
        self.session.query()

    def my_public_keys(self, key_id=None):

        keys = self.session.query(
            PublicKey.id,
            PublicKey.public_key,
            PublicKey.created_on,
            PublicKey.fingerprint,
        ).filter(
            PublicKey.user_id == self.id
        )

        if key_id:
            keys = keys.filter(
                PublicKey.id == key_id
            )

        return keys.all()

    def my_groups(self):

        now = datetime.utcnow()
        groups = self.session.query(
            label("name", Group.groupname),
            label("role", GroupEdge._role)
        ).filter(
            GroupEdge.group_id == Group.id,
            GroupEdge.member_pk == self.id,
            GroupEdge.member_type == 0,
            GroupEdge.active == True,
            self.enabled == True,
            Group.enabled == True,
            or_(
                GroupEdge.expiration > now,
                GroupEdge.expiration == None
            )
        ).all()

        return groups


def build_changes(edge, **updates):
    changes = {}
    for key, value in updates.items():
        if key not in ("role", "expiration", "active"):
            continue
        if getattr(edge, key) != value:
            changes[key] = value
    return json.dumps(changes)


class Group(Model):

    __tablename__ = "groups"

    id = Column(Integer, primary_key=True)
    groupname = Column(String(length=32), unique=True, nullable=False)
    description = Column(Text)
    canjoin = Column(Enum(*GROUP_JOIN_CHOICES), default="canask")
    enabled = Column(Boolean, default=True, nullable=False)

    @hybrid_property
    def name(self):
        return self.groupname

    @flush_transaction
    def revoke_member(self, requester, user_or_group, reason):
        """ Revoke a member (User or Group) from this group.

            Arguments:
                requester: A User object of the person requesting the addition
                user_or_group: A User/Group object of the member
                reason: A comment on why this member should exist
        """
        now = datetime.utcnow()
        member_type = user_or_group.member_type

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
            on_behalf_obj_type=member_type,
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
            obj_type=3,
            obj_pk=request_status_change.id,
            user_id=requester.id,
            comment=reason,
            created_on=now
        ).add(self.session)

        edge.apply_changes(request)
        self.session.flush()

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
                role: member/manager/owner of the Group.
        """
        now = datetime.utcnow()
        member_type = user_or_group.member_type

        # Force role to member when member is a group.
        if member_type == 1:
            role = "member"

        logging.debug(
            "Adding member (%s) to %s", user_or_group.name, self.groupname
        )

        edge, new = GroupEdge.get_or_create(
            self.session,
            group_id=self.id,
            member_type=member_type,
            member_pk=user_or_group.id,
        )
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

    def my_members(self):

        parent = aliased(Group)
        group_member = aliased(Group)
        user_member = aliased(User)

        now = datetime.utcnow()

        users = self.session.query(
            label("type", literal("User")),
            label("membername", user_member.username),
            label("role", GroupEdge._role),
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
            "type", "membername"
        ).subquery()

        groups = self.session.query(
            label("type", literal("Group")),
            label("membername", group_member.groupname),
            label("role", GroupEdge._role),
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
            "type", "membername", "role", "expiration"
        ).select_entity_from(
            union_all(users.select(), groups.select())
        ).order_by(
            desc("role"), desc("type")
        )

        return OrderedDict(
            ((record.type, record.membername), record)
            for record in query.all()
        )

    def my_groups(self):

        now = datetime.utcnow()
        groups = self.session.query(
            label("name", Group.groupname),
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

    def my_requests(self, status=None, user=None):

        members = self.session.query(
            label("type", literal(1)),
            label("id", Group.id),
            label("membername", Group.groupname)
        ).union(self.session.query(
            label("type", literal(0)),
            label("id", User.id),
            label("membername", User.username)
        )).subquery()

        requests = self.session.query(
            Request.id,
            Request.requested_at,
            GroupEdge.expiration,
            Request.status,
            label("requester", User.username),
            label("type", members.c.type),
            label("requesting", members.c.membername),
            label("reason", Comment.comment)
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


class Request(Model):

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
            obj_type=3,
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


class RequestStatusChange(Model):

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
        self._role = GROUP_EDGE_ROLES.index(role)

    def apply_changes(self, request):
        changes = json.loads(request.changes)
        for key, value in changes.items():
            setattr(self, key, value)

    def __repr__(self):
        return "%s(group_id=%s, member_type=%s, member_pk=%s)" % (
            type(self).__name__, self.group_id,
            OBJ_TYPES_IDX[self.member_type], self.member_pk
        )


class Comment(Model):

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)

    obj_type = Column(Integer, nullable=False)
    obj_pk = Column(Integer, nullable=False)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship(User, foreign_keys=[user_id])

    comment = Column(Text, nullable=False)

    created_on = Column(DateTime, default=datetime.utcnow,
                        onupdate=func.current_timestamp(), nullable=False)


class Counter(Model):

    __tablename__ = "counters"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    count = Column(Integer, nullable=False, default=0)
    last_modified = Column(DateTime, default=datetime.utcnow, nullable=False)

    @classmethod
    def incr(cls, session, name, count=1):
        counter = session.query(cls).filter_by(name=name).scalar()
        if counter is None:
            counter = cls(name=name, count=count).add(session)
            session.flush()
            return counter
        counter.count = cls.count + count
        session.flush()
        return counter

    @classmethod
    def decr(cls, session, name, count=1):
        return cls.incr(session, name, -count)


class PublicKey(Model):

    __tablename__ = "public_keys"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship(User, foreign_keys=[user_id])

    public_key = Column(Text, nullable=False, unique=True)
    fingerprint = Column(Text, nullable=False)
    created_on = Column(DateTime, default=datetime.utcnow,
                        onupdate=func.current_timestamp(), nullable=False)
