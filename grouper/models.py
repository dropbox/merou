from annex import Annex
from collections import OrderedDict, namedtuple
from datetime import datetime
import functools
import json
import logging
import re

from sqlalchemy import create_engine
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, UniqueConstraint,
    ForeignKey, Enum, DateTime, SmallInteger, Index
)
from sqlalchemy import or_, union_all, asc, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, object_session
from sqlalchemy.orm import aliased
from sqlalchemy.orm import sessionmaker, Session as _Session
from sqlalchemy.sql import func, label, literal

from .capabilities import Capabilities
from .constants import (
    ARGUMENT_VALIDATION, PERMISSION_GRANT, PERMISSION_CREATE, MAX_NAME_LENGTH,
    PERMISSION_VALIDATION
)
from .plugin import BasePlugin
from .util import matches_glob


OBJ_TYPES_IDX = ("User", "Group", "Request", "RequestStatusChange")
OBJ_TYPES = {obj_type: idx for idx, obj_type in enumerate(OBJ_TYPES_IDX)}

GROUP_JOIN_CHOICES = {
    # Anyone can join with automatic approval
    "canjoin": "actioned",
    # Anyone can ask to join this group
    "canask": "pending",
    # Only those invited may join (should never be a valid status because no
    # join request should be generated for such groups!)
    "nobody": "<integrityerror>",
}

REQUEST_STATUS_CHOICES = {
    # Request has been made and awaiting action.
    "pending": set(["actioned", "cancelled"]),
    "actioned": set([]),
    "cancelled": set([]),
}
GROUP_EDGE_ROLES = (
    "member",    # Belongs to the group. Nothing more.
    "manager",   # Make changes to the group / Approve requests.
    "owner",     # Same as manager plus enable/disable group and make Users owner.
    "np-owner",  # Same as owner but don't inherit permissions.
)

MappedPermission = namedtuple('MappedPermission',
                              ['permission', 'audited', 'argument', 'groupname', 'granted_on'])


class Session(_Session):
    """ Custom session meant to utilize add on the model.

        This Session overrides the add/add_all methods to prevent them
        from being used. This is to for using the add methods on the
        models themselves where overriding is available.
    """

    _add = _Session.add
    _add_all = _Session.add_all
    _delete = _Session.delete

    def add(self, *args, **kwargs):
        raise NotImplementedError("Use add method on models instead.")

    def add_all(self, *args, **kwargs):
        raise NotImplementedError("Use add method on models instead.")

    def delete(self, *args, **kwargs):
        raise NotImplementedError("Use delete method on models instead.")


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
    def get(cls, session, **kwargs):
        instance = session.query(cls).filter_by(**kwargs).scalar()
        if instance:
            return instance
        return None

    @classmethod
    def get_or_create(cls, session, **kwargs):
        instance = session.query(cls).filter_by(**kwargs).scalar()
        if instance:
            return instance, False

        instance = cls(**kwargs)
        instance.add(session)

        cls.just_created(instance)

        return instance, True

    def just_created(self):
        pass

    def add(self, session):
        session._add(self)
        return self

    def delete(self, session):
        session._delete(self)
        return self


Model = declarative_base(cls=Model)


def get_db_engine(url):
    return create_engine(url, pool_recycle=300)


Plugins = []


class PluginsAlreadyLoaded(Exception):
    pass


def load_plugins(plugin_dir, service_name):
    """Load plugins from a directory"""
    global Plugins
    if Plugins:
        raise PluginsAlreadyLoaded("Plugins already loaded; can't load twice!")
    Plugins = Annex(BasePlugin, [plugin_dir], raise_exceptions=True)
    for plugin in Plugins:
        plugin.configure(service_name)

def get_plugins():
    """Get a list of loaded plugins."""
    global Plugins
    return list(Plugins)

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


def get_all_groups(session):
    """Returns all enabled groups.

    At present, this is not cached at all and returns the full list of
    groups from the database each time it's called.

    Args:
        session (Session): Session to load data on.

    Returns:
        a list of all Group objects in the database
    """
    return session.query(Group).filter(Group.enabled == True)


def get_all_users(session):
    """Returns all valid users in the group.

    At present, this is not cached at all and returns the full list of
    users from the database each time it's called.

    Args:
        session (Session): Session to load data on.

    Returns:
        a list of all User objects in the database
    """
    return session.query(User).all()


def get_user_or_group(session, name, user_or_group=None):
    """Given a name, fetch a user or group

    If user_or_group is not defined, we determine whether a the name refers to
    a user or group by checking whether the name is an email address, since
    that's how users are specified.

    Args:
        session (Session): Session to load data on.
        name (str): The name of the user or group.
        user_or_group(str): "user" or "group" to specify the type explicitly

    Returns:
        User or Group object.
    """
    if user_or_group is not None:
        assert (user_or_group in ["user", "group"]), ("%s not in ['user', 'group']" % user_or_group)
        is_user = (user_or_group == "user")
    else:
        is_user = '@' in name

    if is_user:
        return session.query(User).filter_by(username=name).scalar()
    else:
        return session.query(Group).filter_by(groupname=name).scalar()


class User(Model):

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(length=MAX_NAME_LENGTH), unique=True, nullable=False)
    capabilities = Column(Integer, default=0, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    @hybrid_property
    def name(self):
        return self.username

    @property
    def type(self):
        return "User"

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

    def just_created(self):
        for plugin in Plugins:
            plugin.user_created(self)

    def enable(self):
        self.enabled = True
        Counter.incr(self.session, "updates")

    def can_manage(self, group):
        """Determine if this user can manage the given group

        This returns true if this user object is a manager, owner, or np-owner of the given group.

        Args:
            group (Group): Group to check permissions against.

        Returns:
            bool: True or False on whether or not they can manage.
        """
        if not group:
            return False
        members = group.my_members()
        if self.my_role(members) in ("owner", "np-owner", "manager"):
            return True
        return False

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

    @property
    def permission_admin(self):
        return Capabilities(self.capabilities).has("permission_admin")

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
        # TODO(gary) Do.
        self.session.query()

    def set_metadata(self, key, value):
        if not re.match(PERMISSION_VALIDATION, key):
            raise ValueError('Metadata key does not match regex.')

        row = None
        for try_row in self.my_metadata():
            if try_row.data_key == key:
                row = try_row
                break

        if row:
            if value is None:
                row.delete(self.session)
            else:
                row.data_value = value
        else:
            if value is None:
                # Do nothing, a delete on a key that's not set
                return
            else:
                row = UserMetadata(user_id=self.id, data_key=key, data_value=value)
                row.add(self.session)

        Counter.incr(self.session, "updates")
        self.session.commit()

    def my_metadata(self):

        md_items = self.session.query(
            UserMetadata
        ).filter(
            UserMetadata.user_id == self.id
        )

        return md_items.all()

    def my_public_keys(self):

        keys = self.session.query(
            PublicKey.id,
            PublicKey.public_key,
            PublicKey.created_on,
            PublicKey.fingerprint,
        ).filter(
            PublicKey.user_id == self.id
        )

        return keys.all()

    def my_log_entries(self):

        return AuditLog.get_entries(self.session, involve_user_id=self.id, limit=20)

    def my_permissions(self):

        # TODO: Make this walk the tree, so we can get a user's entire set of permissions.
        now = datetime.utcnow()
        permissions = self.session.query(
            Permission.name,
            PermissionMap.argument,
            PermissionMap.granted_on,
            Group,
        ).filter(
            PermissionMap.permission_id == Permission.id,
            PermissionMap.group_id == Group.id,
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
        ).order_by(
            asc("name"), asc("argument"), asc("groupname")
        ).all()

        return permissions

    def my_creatable_permissions(self):
        '''
        Returns a list of permissions this user is allowed to create. Presently, this only counts
        permissions that a user has directly -- in other words, the 'create' permissions are not
        counted as inheritable.

        TODO: consider making these permissions inherited? This requires walking the graph, which
        is expensive.

        Returns a list of strings that are to be interpreted as glob strings. You should use the
        util function matches_glob.
        '''
        if self.permission_admin:
            return '*'

        # Someone can grant a permission if they are a member of a group that has a permission
        # of PERMISSION_GRANT with an argument that matches the name of a permission.
        return [
            permission.argument
            for permission in self.my_permissions()
            if permission.name == PERMISSION_CREATE
        ]

    def my_grantable_permissions(self):
        '''
        Returns a list of permissions this user is allowed to grant. Presently, this only counts
        permissions that a user has directly -- in other words, the 'grant' permissions are not
        counted as inheritable.

        TODO: consider making these permissions inherited? This requires walking the graph, which
        is expensive.

        Returns a list of tuples (Permission, argument) that the user is allowed to grant.
        '''
        all_permissions = {permission.name: permission
                           for permission in Permission.get_all(self.session)}
        if self.permission_admin:
            result = [(perm, '*') for perm in all_permissions.values()]
            return sorted(result, key=lambda x: x[0].name + x[1])

        # Someone can grant a permission if they are a member of a group that has a permission
        # of PERMISSION_GRANT with an argument that matches the name of a permission.
        result = []
        for permission in self.my_permissions():
            if permission.name != PERMISSION_GRANT:
                continue
            grantable = permission.argument.split('/', 1)
            if not grantable:
                continue
            for name, permission_obj in all_permissions.iteritems():
                if matches_glob(grantable[0], name):
                    result.append((permission_obj,
                                   grantable[1] if len(grantable) > 1 else '*', ))
        return sorted(result, key=lambda x: x[0].name + x[1])

    def my_groups(self):

        now = datetime.utcnow()
        groups = self.session.query(
            label("name", Group.groupname),
            label("type", literal("Group")),
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

    def my_requests_aggregate(self):
        """Returns all pending requests for this user to approve across groups."""
        members = self.session.query(
            label("type", literal(1)),
            label("id", Group.id),
            label("name", Group.groupname),
        ).union(self.session.query(
            label("type", literal(0)),
            label("id", User.id),
            label("name", User.username),
        )).subquery()

        now = datetime.utcnow()
        groups = self.session.query(
            label("id", Group.id),
            label("name", Group.groupname),
        ).filter(
            GroupEdge.group_id == Group.id,
            GroupEdge.member_pk == self.id,
            GroupEdge.active == True,
            GroupEdge._role.in_([1, 2]),
            self.enabled == True,
            Group.enabled == True,
            or_(
                GroupEdge.expiration > now,
                GroupEdge.expiration == None,
            )
        ).subquery()

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
            label("group_id", groups.c.id),
            label("groupname", groups.c.name),
        ).filter(
            Request.on_behalf_obj_pk == members.c.id,
            Request.on_behalf_obj_type == members.c.type,
            Request.requesting_id == groups.c.id,
            Request.requester_id == User.id,
            Request.status == "pending",
            Request.id == RequestStatusChange.request_id,
            RequestStatusChange.from_status == None,
            GroupEdge.id == Request.edge_id,
            Comment.obj_type == 3,
            Comment.obj_pk == RequestStatusChange.id,
        )

        return requests


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
    def grant_permission(self, permission, argument=''):
        """
        Grant a permission to this group. This will fail if the (permission, argument) has already
        been granted to this group.

        Arguments:
            permission: a Permission object being granted
            argument: must match constants.ARGUMENT_VALIDATION
        """
        if not re.match(ARGUMENT_VALIDATION, argument):
            raise ValueError('Permission argument does not match regex.')

        mapping = PermissionMap(permission_id=permission.id, group_id=self.id,
                                argument=argument)
        mapping.add(self.session)

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

        # Force role to member when member is a group. Just in case.
        if member_type == 1 and "role" in kwargs:
            kwargs["role"] = "member"

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
            obj_type=3,
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

    def my_log_entries(self):

        return AuditLog.get_entries(self.session, on_group_id=self.id, limit=20)

    def my_members(self):

        parent = aliased(Group)
        group_member = aliased(Group)
        user_member = aliased(User)

        now = datetime.utcnow()

        users = self.session.query(
            label("id", user_member.id),
            label("type", literal("User")),
            label("name", user_member.username),
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
            "type", "name"
        ).subquery()

        groups = self.session.query(
            label("id", group_member.id),
            label("type", literal("Group")),
            label("name", group_member.groupname),
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
            "id", "type", "name", "role", "expiration"
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
            if key == 'expiration':
                if value:
                    setattr(self, key, datetime.strptime(value, "%m/%d/%Y"))
                else:
                    setattr(self, key, None)
            else:
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


class UserMetadata(Model):

    __tablename__ = "user_metadata"
    __table_args__ = (
        UniqueConstraint('user_id', 'data_key', name='uidx1'),
    )

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship(User, foreign_keys=[user_id])

    data_key = Column(String(length=64), nullable=False)
    data_value = Column(String(length=64), nullable=False)
    last_modified = Column(DateTime, default=datetime.utcnow, nullable=False)

    def add(self, session):
        super(UserMetadata, self).add(session)
        Counter.incr(session, "updates")
        return self

    def delete(self, session):
        super(UserMetadata, self).delete(session)
        Counter.incr(session, "updates")
        return self


class PublicKey(Model):

    __tablename__ = "public_keys"

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship(User, foreign_keys=[user_id])

    public_key = Column(Text, nullable=False, unique=True)
    fingerprint = Column(String(length=64), nullable=False)
    created_on = Column(DateTime, default=datetime.utcnow, nullable=False)

    def add(self, session):
        super(PublicKey, self).add(session)
        Counter.incr(session, "updates")
        return self

    def delete(self, session):
        super(PublicKey, self).delete(session)
        Counter.incr(session, "updates")
        return self


class Permission(Model):
    '''
    Represents permission types. See PermissionEdge for the mapping of which permissions
    exist on a given Group.
    '''

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)

    name = Column(String(length=64), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    created_on = Column(DateTime, default=datetime.utcnow, nullable=False)
    _audited = Column('audited', Boolean, default=False, nullable=False)

    @staticmethod
    def get(session, name=None):
        if name is not None:
            return session.query(Permission).filter_by(name=name).scalar()
        return None

    @staticmethod
    def get_all(session):
        return session.query(Permission).order_by(asc("name")).all()

    @property
    def audited(self):
        return self._audited

    def enable_auditing(self):
        self._audited = True
        Counter.incr(self.session, "updates")

    def disable_auditing(self):
        self._audited = False
        Counter.incr(self.session, "updates")

    def get_mapped_groups(self):
        '''
        Return a list of tuples: (Group object, argument).
        '''
        results = self.session.query(
            Group.groupname,
            PermissionMap.argument,
            PermissionMap.granted_on,
        ).filter(
            Group.id == PermissionMap.group_id,
            PermissionMap.permission_id == self.id,
        )
        return results.all()

    def my_log_entries(self):

        return AuditLog.get_entries(self.session, on_permission_id=self.id, limit=20)


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


class PermissionMap(Model):
    '''
    Maps a relationship between a Permission and a Group. Note that a single permission can be
    mapped into a given group multiple times, as long as the argument is unique.

    These include the optional arguments, which can either be a string, an asterisks ("*"), or
    Null to indicate no argument.
    '''

    __tablename__ = "permissions_map"
    __table_args__ = (
        UniqueConstraint('permission_id', 'group_id', 'argument', name='uidx1'),
    )

    id = Column(Integer, primary_key=True)

    permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=False)
    permission = relationship(Permission, foreign_keys=[permission_id])

    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group = relationship(Group, foreign_keys=[group_id])

    argument = Column(String(length=64), nullable=True)
    granted_on = Column(DateTime, default=datetime.utcnow, nullable=False)

    @staticmethod
    def get(session, id=None):
        if id is not None:
            return session.query(PermissionMap).filter_by(id=id).scalar()
        return None

    def add(self, session):
        super(PermissionMap, self).add(session)
        Counter.incr(session, "updates")
        return self

    def delete(self, session):
        super(PermissionMap, self).delete(session)
        Counter.incr(session, "updates")
        return self


class AuditLogFailure(Exception):
    pass


class AuditLog(Model):
    '''
    Logs actions taken in the system. This is a pretty simple logging framework to just
    let us track everything that happened. The main use case is to show users what has
    happened recently, to help them understand.
    '''

    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    log_time = Column(DateTime, default=datetime.utcnow, nullable=False)

    # The actor is the person who took an action.
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor = relationship(User, foreign_keys=[actor_id])

    # The 'on_*' columns are what was acted on.
    on_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    on_user = relationship(User, foreign_keys=[on_user_id])
    on_group_id = Column(Integer, ForeignKey("groups.id"), nullable=True)
    on_group = relationship(Group, foreign_keys=[on_group_id])
    on_permission_id = Column(Integer, ForeignKey("permissions.id"), nullable=True)
    on_permission = relationship(Permission, foreign_keys=[on_permission_id])

    # The action and description columns are text. These are mostly displayed
    # to the user as-is, but we might provide filtering or something.
    action = Column(String(length=64), nullable=False)
    description = Column(Text, nullable=False)

    @staticmethod
    def log(session, actor_id, action, description,
            on_user_id=None, on_group_id=None, on_permission_id=None):
        '''
        Log an event in the database.
        '''
        entry = AuditLog(
            actor_id=actor_id,
            log_time=datetime.utcnow(),
            action=action,
            description=description,
            on_user_id=on_user_id if on_user_id else None,
            on_group_id=on_group_id if on_group_id else None,
            on_permission_id=on_permission_id if on_permission_id else None,
        )
        try:
            entry.add(session)
            session.flush()
        except IntegrityError:
            session.rollback()
            raise AuditLogFailure()
        session.commit()

    @staticmethod
    def get_entries(session, actor_id=None, on_user_id=None, on_group_id=None,
                    on_permission_id=None, limit=None, offset=None, involve_user_id=None):
        '''
        Flexible method for getting log entries. By default it returns all entries
        starting at the newest. Most recent first.

        involve_user_id, if set, is (actor_id OR on_user_id).
        '''

        results = session.query(AuditLog)

        if actor_id:
            results = results.filter(AuditLog.actor_id == actor_id)
        if on_user_id:
            results = results.filter(AuditLog.on_user_id == on_user_id)
        if on_group_id:
            results = results.filter(AuditLog.on_group_id == on_group_id)
        if on_permission_id:
            results = results.filter(AuditLog.on_permission_id == on_permission_id)
        if involve_user_id:
            results = results.filter(or_(
                AuditLog.on_user_id == involve_user_id,
                AuditLog.actor_id == involve_user_id
            ))

        results = results.order_by(desc(AuditLog.log_time))

        if offset:
            results = results.offset(offset)
        if limit:
            results = results.limit(limit)

        return results.all()
