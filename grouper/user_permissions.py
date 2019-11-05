from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import asc, or_

from grouper.constants import (
    GROUP_ADMIN,
    PERMISSION_ADMIN,
    PERMISSION_CREATE,
    PERMISSION_GRANT,
    USER_ADMIN,
)
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.permission import Permission
from grouper.models.permission_map import PermissionMap

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.models.user import User
    from typing import List, Optional


def user_has_permission(session, user, permission, argument=None):
    # type: (Session, User, str, Optional[str]) -> bool
    """See if this user has a given permission/argument

    NOTE: only enabled permissions are considered.

    This walks a user's permissions (local/direct only) and determines if they have the given
    permission. If an argument is specified, return True only if they have exactly that argument
    or if they have the wildcard ('*') argument.
    """
    for perm in user_permissions(session, user):
        if perm.name != permission:
            continue
        if perm.argument == "*" or argument is None:
            return True
        if perm.argument == argument:
            return True
    return False


def user_permissions(session, user):
    """Return a user's enabled permissions"""

    # TODO: Make this walk the tree, so we can get a user's entire set of permissions.
    now = datetime.utcnow()
    permissions = (
        session.query(Permission.name, PermissionMap.argument, PermissionMap.granted_on, Group)
        .filter(
            PermissionMap.permission_id == Permission.id,
            PermissionMap.group_id == Group.id,
            GroupEdge.group_id == Group.id,
            GroupEdge.member_pk == user.id,
            GroupEdge.member_type == 0,
            GroupEdge.active == True,
            user.enabled == True,
            Group.enabled == True,
            or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
        )
        .order_by(asc("name"), asc("argument"), asc("groupname"))
        .all()
    )

    return permissions


def user_grantable_permissions(session, user):
    """
    Returns a list of permissions this user is allowed to grant. Presently, this only counts
    permissions that a user has directly -- in other words, the 'grant' permissions are not
    counted as inheritable.

    TODO: consider making these permissions inherited? This requires walking the graph, which
    is expensive.

    Returns a list of tuples (Permission, argument) that the user is allowed to grant.
    """
    # avoid circular dependency
    from grouper.permissions import filter_grantable_permissions, get_all_permissions

    all_permissions = {permission.name: permission for permission in get_all_permissions(session)}
    if user_is_permission_admin(session, user):
        result = ((perm, "*") for perm in all_permissions.values())
        return sorted(result, key=lambda x: x[0].name + x[1])

    # Someone can grant a permission if they are a member of a group that has a permission
    # of PERMISSION_GRANT with an argument that matches the name of a permission.
    grants = [x for x in user_permissions(session, user) if x.name == PERMISSION_GRANT]
    return filter_grantable_permissions(session, grants)


def user_creatable_permissions(session, user):
    # type: (Session, User) -> List[str]
    """
    Returns a list of permissions this user is allowed to create. Presently, this only counts
    permissions that a user has directly -- in other words, the 'create' permissions are not
    counted as inheritable.

    TODO: consider making these permissions inherited? This requires walking the graph, which
    is expensive.

    Returns a list of strings that are to be interpreted as glob strings. You should use the
    util function matches_glob.
    """
    if user_is_permission_admin(session, user):
        return ["*"]

    # Someone can create a permission if they are a member of a group that has a permission
    # of PERMISSION_CREATE with an argument that matches the name of a permission.
    return [
        permission.argument
        for permission in user_permissions(session, user)
        if permission.name == PERMISSION_CREATE
    ]


def user_is_user_admin(session, user):
    return user_has_permission(session, user, USER_ADMIN)


def user_is_group_admin(session, user):
    return user_has_permission(session, user, GROUP_ADMIN)


def user_is_permission_admin(session, user):
    return user_has_permission(session, user, PERMISSION_ADMIN)
