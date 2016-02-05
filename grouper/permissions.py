from collections import defaultdict
from datetime import datetime

from grouper.constants import PERMISSION_GRANT
from grouper.email_util import send_email
from grouper.fe.settings import settings
from grouper.models import (Comment, Group, Permission, PermissionMap,
        PermissionRequest, PermissionRequestStatusChange)
from grouper.models import OBJ_TYPES_IDX
from grouper.plugin import get_plugins
from grouper.util import matches_glob


def filter_grantable_permissions(session, grants, all_permissions=None):
    """For a given set of PERMISSION_GRANT permissions, return all permissions
    that are grantable.

    Args:
        session (sqlalchemy.orm.session.Session); database session
        grants ([Permission, ...]): PERMISSION_GRANT permissions
        all_permissions ({name: Permission}): all permissions to check against

    Returns:
        list of (Permission, argument) that is grantable by list of grants
        sorted by permission name and argument.
    """

    if all_permissions is None:
        all_permissions = {permission.name: permission for permission in
                Permission.get_all(session)}

    result = []
    for grant in grants:
        assert grant.name == PERMISSION_GRANT

        grantable = grant.argument.split('/', 1)
        if not grantable:
            continue
        for name, permission_obj in all_permissions.iteritems():
            if matches_glob(grantable[0], name):
                result.append((permission_obj,
                               grantable[1] if len(grantable) > 1 else '*', ))

    return sorted(result, key=lambda x: x[0].name + x[1])


def get_owners_by_grantable_permission(session):
    """
    Returns all known permission arguments with owners. This consolidates
    permission grants supported by grouper itself as well as any grants
    governed by plugins.

    Args:
        session(sqlalchemy.orm.session.Session): database session

    Returns:
        A map of permission+argument to owners of the form
        defaultdict({(permission, argument): [owner1, owner2, ...], ...}) where
        'owners' are models.Group objects. And 'argument' can be '*' which
        means 'anything'.
    """
    all_permissions = {permission.name: permission for permission in Permission.get_all(session)}
    all_groups = session.query(Group).filter(Group.enabled == True).all()

    owners_by_perm_arg = defaultdict(list)
    for group in all_groups:
        grants = session.query(
                Permission.name,
                PermissionMap.argument,
                PermissionMap.granted_on,
                Group,
        ).filter(
                PermissionMap.group_id == Group.id,
                Group.id == group.id,
                Permission.id == PermissionMap.permission_id,
                Permission.name == PERMISSION_GRANT,
        ).all()

        for perm, arg in filter_grantable_permissions(session, grants,
                all_permissions=all_permissions):
            owners_by_perm_arg[(perm.name, arg)].append(group)

    # merge in plugin results
    for plugin in get_plugins():
        for perm_arg, owners in plugin.get_perm_arg_to_owners(session).items():
            owners_by_perm_arg[perm_arg] += owners

    return owners_by_perm_arg


def get_grantable_permissions(session):
    """Returns all grantable permissions and their possible arguments. This
    function attempts to reduce a permission's arguments to the most
    permissive, i.e. if a wildcard argument exists, everything else is
    discarded.

    Args:
        session(sqlalchemy.orm.session.Session): database session

    Returns:
        A map of models.Permission object to a list of possible arguments, i.e.
        {models.Permission: [arg1, arg2, ...], ...}
    """
    owners_by_perm_arg = get_owners_by_grantable_permission(session)
    args_by_perm = defaultdict(list)
    for permission, argument in owners_by_perm_arg.keys():
        args_by_perm[permission].append(argument)

    def _reduce_args(args):
        return "*" if len(args) > 1 and "*" in args else args
    return {p: _reduce_args(a) for p, a in args_by_perm.items()}


def get_owners(session, permission, argument):
    """Return the grouper group(s) responsible for approving a request for the
    given permission + argument.

    Args:
        session(): database session
        permission(models.Permission): permission in question
        argument(str): argument for the permission
    Returns:
        list of models.Group grouper groups responsibile for
        permimssion+argument. can be empty.
    """
    owner_by_perm_arg = get_owners_by_grantable_permission(session)

    owners = (owner_by_perm_arg[(permission.name, "*")] +
            owner_by_perm_arg[(permission.name, argument)])

    return list(set(owners))


class PermissionRequestException(Exception):
    pass


class RequestAlreadyExists(PermissionRequestException):
    """Trying to create a request for a permission + argument + group which
    already exists in "pending" state."""


class NoOwnersAvailable(PermissionRequestException):
    """No owner was found for the permission + argument combination."""


class InvalidRequestID(PermissionRequestException):
    """Submitted request ID is invalid (doesn't exist or group doesn't match."""


def create_request(session, user, group, permission, argument, reason):
    """
    Creates an permission request and sends notification to the responsible approvers.

    Args:
        session(sqlalchemy.orm.session.Session): database session
        user(models.User): user requesting permission
        group(models.Group): group requested permission would be applied to
        permission(models.Permission): permission in question to request
        argument(str): argument for the given permission
        reason(str): reason the permission should be granted

    Raises:
        RequestAlreadyExists if trying to create a request that is already pending
        NoOwnersAvailable if no owner is available for the requested perm + arg.
    """
    # check if request already pending for this perm + arg pair
    existing_count = session.query(PermissionRequest).filter(
            PermissionRequest.group_id == group.id,
            PermissionRequest.permission_id == permission.id,
            PermissionRequest.argument == argument,
            PermissionRequest.status == "pending",
            ).count()

    if existing_count > 0:
        raise RequestAlreadyExists()

    # determine owner(s)
    owners = get_owners(session, permission, argument)

    if not owners:
        raise NoOwnersAvailable()

    pending_status = "pending"
    now = datetime.utcnow()

    # multiple steps to create the request
    request = PermissionRequest(
            requester_id=user.id,
            group_id=group.id,
            permission_id=permission.id,
            argument=argument,
            status=pending_status,
            requested_at=now,
            ).add(session)
    session.flush()

    request_status_change = PermissionRequestStatusChange(
            request=request,
            user=user,
            to_status=pending_status,
            change_at=now,
            ).add(session)
    session.flush()

    Comment(
            obj_type=OBJ_TYPES_IDX.index("PermissionRequestStatusChange"),
            obj_pk=request_status_change.id,
            user_id=user.id,
            comment=reason,
            created_on=now,
            ).add(session)

    # send notification
    email_context = {
            "user_name": user.name,
            "group_name": group.name,
            "permission_name": permission.name,
            "argument": argument,
            "reason": reason,
            }

    # TODO: would be nicer if it told you which group you're an approver of
    # that's causing this notification
    mail_to = []
    for owner in owners:
        mail_to += [u.name for u in owner.my_members()]
    send_email(session, mail_to, "Request for permission: {}".format(permission.name),
            "pending_permission_request", settings, email_context)


def get_pending_request_by_group(session, group):
    """Load pending request for a particular group.

    Args:
        session(sqlalchemy.orm.session.Session): database session
        group(models.Group): group in question

    Returns:
        list of models.PermissionRequest correspodning to open/pending requests
        for this group.
    """
    return session.query(PermissionRequest).filter(
            PermissionRequest.status == "pending",
            PermissionRequest.group_id == group.id,
            ).all()
