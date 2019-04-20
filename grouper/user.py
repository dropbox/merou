from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import or_
from sqlalchemy.sql import label, literal

from grouper.entities.group_edge import APPROVER_ROLE_INDICES, GROUP_EDGE_ROLES, OWNER_ROLE_INDICES
from grouper.models.audit import Audit
from grouper.models.audit_log import AuditLog
from grouper.models.comment import Comment
from grouper.models.counter import Counter
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.request import Request
from grouper.models.request_status_change import RequestStatusChange
from grouper.models.user import User
from grouper.plugin import get_plugin_proxy
from grouper.user_group import get_groups_by_user
from grouper.user_permissions import user_is_group_admin

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import List


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
        assert user_or_group in ["user", "group"], "%s not in ['user', 'group']" % user_or_group
        is_user = user_or_group == "user"
    else:
        is_user = "@" in name

    if is_user:
        return session.query(User).filter_by(username=name).scalar()
    else:
        return session.query(Group).filter_by(groupname=name).scalar()


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


def get_all_enabled_users(session, include_service_accounts=True):
    # type: (Session, bool) -> List[User]
    """Returns all enabled users in the database.

    At present, this is not cached at all and returns the full list of
    users from the database each time it's called.

    Args:
        session (Session): Session to load data on.

    Returns:
        a list of all enabled User objects in the database
    """
    if include_service_accounts:
        return session.query(User).filter_by(enabled=True).all()
    return session.query(User).filter(User.enabled == True).filter(User.role_user == False).all()


def enable_user(session, user, requester, preserve_membership):
    """Enable a disabled user.

    Args:
        preserve_membership(bool): whether to remove user from any groups it may be a member of
    Returns:
        None
    """
    if not preserve_membership:
        for group, group_edge in get_groups_by_user(session, user):
            group_obj = session.query(Group).filter_by(groupname=group.name).scalar()
            if group_obj:
                group_obj.revoke_member(
                    requester, user, "group membership stripped as part of re-enabling account."
                )

    user.enabled = True
    Counter.incr(session, "updates")


def disable_user(session, user):
    """Disables an enabled user"""

    get_plugin_proxy().will_disable_user(session, user)

    user.enabled = False
    Counter.incr(session, "updates")


def user_role_index(user, members):
    if user_is_group_admin(user.session, user):
        return GROUP_EDGE_ROLES.index("owner")
    member = members.get(("User", user.name))
    if not member:
        return None
    return member.role


def user_role(user, members):
    role_index = user_role_index(user, members)
    if role_index is None:
        return None
    else:
        return GROUP_EDGE_ROLES[role_index]


def user_requests_aggregate(session, user):
    """Returns all pending requests for this user to approve across groups."""

    members = (
        session.query(
            label("type", literal(1)), label("id", Group.id), label("name", Group.groupname)
        )
        .union(
            session.query(
                label("type", literal(0)), label("id", User.id), label("name", User.username)
            )
        )
        .subquery()
    )

    now = datetime.utcnow()
    groups = (
        session.query(label("id", Group.id), label("name", Group.groupname))
        .filter(
            GroupEdge.group_id == Group.id,
            GroupEdge.member_pk == user.id,
            GroupEdge.active == True,
            GroupEdge._role.in_(APPROVER_ROLE_INDICES),
            user.enabled == True,
            Group.enabled == True,
            or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
        )
        .subquery()
    )

    requests = session.query(
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


def user_open_audits(session, user):
    session.query(Audit).filter(Audit.complete == False)
    now = datetime.utcnow()
    return (
        session.query(
            label("groupname", Group.groupname),
            label("started_at", Audit.started_at),
            label("ends_at", Audit.ends_at),
        )
        .filter(
            Audit.group_id == Group.id,
            Audit.complete == False,
            GroupEdge.group_id == Group.id,
            GroupEdge.member_pk == user.id,
            GroupEdge.member_type == 0,
            GroupEdge.active == True,
            GroupEdge._role.in_(OWNER_ROLE_INDICES),
            user.enabled == True,
            Group.enabled == True,
            or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
        )
        .all()
    )


def get_log_entries_by_user(session, user, limit=20):
    """For a given user, return the audit logs that pertain.

    Args:
        session(models.base.session.Session): database session
        user(User): user in question
        limit(int): number of results to return
    """
    return AuditLog.get_entries(session, involve_user_id=user.id, limit=limit)
