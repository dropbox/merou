from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import cast, TYPE_CHECKING

from sqlalchemy import asc
from sqlalchemy.exc import IntegrityError

from grouper.audit import assert_controllers_are_auditors
from grouper.constants import ARGUMENT_VALIDATION, PERMISSION_ADMIN, PERMISSION_GRANT
from grouper.email_util import EmailTemplateEngine, send_email
from grouper.models.audit_log import AuditLog
from grouper.models.base.constants import OBJ_TYPES_IDX
from grouper.models.comment import Comment
from grouper.models.counter import Counter
from grouper.models.group import Group
from grouper.models.permission import Permission
from grouper.models.permission_map import PermissionMap
from grouper.models.permission_request import PermissionRequest
from grouper.models.permission_request_status_change import PermissionRequestStatusChange
from grouper.models.service_account_permission_map import ServiceAccountPermissionMap
from grouper.plugin import get_plugin_proxy
from grouper.settings import settings
from grouper.user_group import get_groups_by_user
from grouper.util import matches_glob

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.models.service_account import ServiceAccount
    from grouper.models.user import User
    from typing import Any, Dict, List, Optional, Set, Tuple

# Singleton
GLOBAL_OWNERS = object()


@dataclass(frozen=True)
class Requests:
    """Represents all information we care about for a list of permission requests."""

    requests: List[PermissionRequest]
    status_change_by_request_id: Dict[int, List[PermissionRequestStatusChange]]
    comment_by_status_change_id: Dict[int, Comment]


class NoSuchPermission(Exception):
    """No permission by this name exists."""

    def __init__(self, name: str) -> None:
        self.name = name


def create_permission(
    session: Session, name: str, description: Optional[str] = None
) -> Permission:
    """Create and add a new permission to database."""
    permission = Permission(name=name, description=description or "")
    permission.add(session)
    return permission


def get_all_permissions(session: Session, include_disabled: bool = False) -> List[Permission]:
    """Get permissions that exist in the database.

    Can retrieve either only enabled permissions, or both enabled and disabled ones.

    Args:
        session: Database session
        include_disabled: True to include disabled permissions (make sure you really want this)
    """
    query = session.query(Permission)
    if not include_disabled:
        query = query.filter(Permission.enabled == True)
    return query.order_by(asc(Permission.name)).all()


def get_permission(session: Session, name: str) -> Optional[Permission]:
    return Permission.get(session, name=name)


def get_or_create_permission(
    session: Session, name: str, description: Optional[str] = None
) -> Tuple[Optional[Permission], bool]:
    """Get a permission or create it if it doesn't already exist.

    Returns:
        (permission, is_new) tuple
    """
    perm = get_permission(session, name)
    is_new = False
    if not perm:
        is_new = True
        perm = create_permission(session, name, description=description or "")
    return perm, is_new


def grant_permission(
    session: Session, group_id: int, permission_id: int, argument: str = ""
) -> None:
    """Grant a permission to this group.

    This will fail if the (permission, argument) has already been granted to this group.

    Args:
        session: Database session
        group_id: ID of group to which to grant the permission
        permission_id: ID of permission to grant
        argument: Must match constants.ARGUMENT_VALIDATION

    Throws:
        AssertError if argument does not match ARGUMENT_VALIDATION regex
    """
    assert re.match(ARGUMENT_VALIDATION + r"$", argument), "Invalid permission argument"

    mapping = PermissionMap(permission_id=permission_id, group_id=group_id, argument=argument)
    mapping.add(session)

    Counter.incr(session, "updates")

    session.commit()


def grant_permission_to_service_account(
    session: Session, account: ServiceAccount, permission: Permission, argument: str = ""
) -> None:
    """Grant a permission to this service account.

    This will fail if the (permission, argument) has already been granted to this group.

    Args:
        session: Database session
        account: A ServiceAccount object being granted a permission
        permission: A Permission object being granted
        argument: Must match constants.ARGUMENT_VALIDATION

    Throws:
        AssertError if argument does not match ARGUMENT_VALIDATION regex
    """
    assert re.match(ARGUMENT_VALIDATION + r"$", argument), "Invalid permission argument"

    mapping = ServiceAccountPermissionMap(
        permission_id=permission.id, service_account_id=account.id, argument=argument
    )
    mapping.add(session)

    Counter.incr(session, "updates")

    session.commit()


def enable_permission_auditing(session: Session, permission_name: str, actor_user_id: int) -> None:
    """Set a permission as audited.

    Args:
        session: Database session
        permission_name: Name of permission in question
        actor_user_id: ID of user who is enabling auditing
    """
    permission = get_permission(session, permission_name)
    if not permission:
        raise NoSuchPermission(name=permission_name)

    permission.audited = True

    AuditLog.log(
        session,
        actor_user_id,
        "enable_auditing",
        "Enabled auditing.",
        on_permission_id=permission.id,
    )

    Counter.incr(session, "updates")

    session.commit()


def disable_permission_auditing(
    session: Session, permission_name: str, actor_user_id: int
) -> None:
    """Set a permission as audited.

    Args:
        session: Database session
        permission_name: Name of permission in question
        actor_user_id: ID of user who is disabling auditing
    """
    permission = get_permission(session, permission_name)
    if not permission:
        raise NoSuchPermission(name=permission_name)

    permission.audited = False

    AuditLog.log(
        session,
        actor_user_id,
        "disable_auditing",
        "Disabled auditing.",
        on_permission_id=permission.id,
    )

    Counter.incr(session, "updates")

    session.commit()


def get_groups_by_permission(session: Session, permission: Permission) -> List[Tuple[str, str]]:
    """Return the groups granted a permission and their associated arguments.

    For an enabled permission, return the groups and associated arguments that have that
    permission. If the permission is disabled, return empty list.

    Returns:
        List of 2-tuple of the form (group_name, argument).
    """
    if not permission.enabled:
        return []
    return (
        session.query(Group.groupname, PermissionMap.argument, PermissionMap.granted_on)
        .filter(
            Group.id == PermissionMap.group_id,
            PermissionMap.permission_id == permission.id,
            Group.enabled == True,
        )
        .all()
    )


def filter_grantable_permissions(
    session: Session, grants: List[Any], all_permissions: Optional[Dict[str, Permission]] = None
) -> List[Tuple[Permission, str]]:
    """For a set of PERMISSION_GRANT permissions, return all permissions that are grantable.

    Args:
        session: Database session
        grants: PERMISSION_GRANT permissions
        all_permissions: All permissions to check against (defaults to all permissions)

    Returns:
        List of (Permission, argument) that is grantable by list of grants, sorted by permission
        name and argument.
    """
    if all_permissions is None:
        all_permissions = {
            permission.name: permission for permission in get_all_permissions(session)
        }

    result = []
    for grant in grants:
        assert grant.name == PERMISSION_GRANT

        grantable = grant.argument.split("/", 1)
        if not grantable:
            continue
        for name, permission_obj in all_permissions.items():
            if matches_glob(grantable[0], name):
                result.append((permission_obj, grantable[1] if len(grantable) > 1 else "*"))

    return sorted(result, key=lambda x: x[0].name + x[1])


def get_owners_by_grantable_permission(
    session: Session, separate_global: bool = False
) -> Dict[object, Dict[str, List[Group]]]:
    """Returns all known permission arguments with owners.

    This consolidates permission grants supported by grouper itself as well as any grants governed
    by plugins.

    Args:
        session: Database session
        separate_global: Whether to construct a specific entry for GLOBAL_OWNER in the output map

    Returns:
        A map of permission to argument to owners of the form:
            {permission: {argument: [owner1, ...], }, }
        where owners are Group objects.  argument can be '*' which means anything.
    """
    all_permissions = {permission.name: permission for permission in get_all_permissions(session)}
    all_groups = session.query(Group).filter(Group.enabled == True).all()

    owners_by_arg_by_perm: Dict[object, Dict[str, List[Group]]] = defaultdict(
        lambda: defaultdict(list)
    )

    all_group_permissions = (
        session.query(Permission.name, PermissionMap.argument, PermissionMap.granted_on, Group)
        .filter(PermissionMap.group_id == Group.id, Permission.id == PermissionMap.permission_id)
        .all()
    )

    grants_by_group: Dict[str, List[Any]] = defaultdict(list)

    for grant in all_group_permissions:
        grants_by_group[grant.Group.id].append(grant)

    for group in all_groups:
        # special case permission admins
        group_permissions = grants_by_group[group.id]
        if any([g.name == PERMISSION_ADMIN for g in group_permissions]):
            for perm_name in all_permissions:
                owners_by_arg_by_perm[perm_name]["*"].append(group)
            if separate_global:
                owners_by_arg_by_perm[GLOBAL_OWNERS]["*"].append(group)
            continue

        grants = [gp for gp in group_permissions if gp.name == PERMISSION_GRANT]

        for perm, arg in filter_grantable_permissions(
            session, grants, all_permissions=all_permissions
        ):
            owners_by_arg_by_perm[perm.name][arg].append(group)

        for gp in group_permissions:
            aliases = get_plugin_proxy().get_aliases_for_mapped_permission(
                session, gp.name, gp.argument
            )
            for alias in aliases:
                if alias[0] == PERMISSION_GRANT:
                    alias_perm, arg = alias[1].split("/", 1)
                    owners_by_arg_by_perm[alias_perm][arg].append(group)

    # merge in plugin results
    for res in get_plugin_proxy().get_owner_by_arg_by_perm(session):
        for permission_name, owners_by_arg in res.items():
            for arg, owners in owners_by_arg.items():
                owners_by_arg_by_perm[permission_name][arg] += owners

    return owners_by_arg_by_perm


def get_grantable_permissions(
    session: Session, restricted_ownership_permissions: List[str]
) -> Dict[str, List[str]]:
    """Returns all grantable permissions and their possible arguments.

    This function attempts to reduce a permission's arguments to the least permissive possible.

    Args:
        session: Database session
        restricted_ownership_permissions: List of permissions for which we exclude wildcard
            ownership from the result if any non-wildcard owners exist

    Returns:
        A map of permission names to a list of possible arguments.
    """
    owners_by_arg_by_perm = get_owners_by_grantable_permission(session)
    args_by_perm: Dict[str, List[str]] = defaultdict(list)
    for permission, owners_by_arg in owners_by_arg_by_perm.items():
        for argument in owners_by_arg:
            args_by_perm[cast(str, permission)].append(argument)

    def _reduce_args(perm_name: str, args: List[str]) -> List[str]:
        non_wildcard_args = [a != "*" for a in args]
        if (
            restricted_ownership_permissions
            and perm_name in restricted_ownership_permissions
            and any(non_wildcard_args)
        ):
            # at least one none wildcard arg so we only return those and we care
            return sorted({a for a in args if a != "*"})
        elif all(non_wildcard_args):
            return sorted(set(args))
        else:
            # it's all wildcard so return that one
            return ["*"]

    return {p: _reduce_args(p, a) for p, a in args_by_perm.items()}


def get_owner_arg_list(
    session: Session,
    permission: Permission,
    argument: str,
    owners_by_arg_by_perm: Optional[Dict[object, Dict[str, List[Group]]]] = None,
) -> List[Tuple[Group, str]]:
    """Determine the Grouper groups responsible for approving a request.

    Return the grouper groups responsible for approving a request for the given permission +
    argument along with the actual argument they were granted.

    Args:
        session: Database session
        permission: Permission in question
        argument: Argument for the permission
        owners_by_arg_by_perm: Groups that can grant a given permission, argument pair in the
            format of {perm_name: {argument: [group1, group2, ...], ...}, ...}
            This is for convenience/caching if the value has already been fetched.

    Returns:
        List of 2-tuple of (group, argument) where group is the Group for the Grouper groups
        responsibile for permimssion + argument, and argument is the argument actually granted to
        that group. Can be empty.
    """
    if owners_by_arg_by_perm is None:
        owners_by_arg_by_perm = get_owners_by_grantable_permission(session)

    all_owner_arg_list: List[Tuple[Group, str]] = []
    owners_by_arg = owners_by_arg_by_perm[permission.name]
    for arg, owners in owners_by_arg.items():
        if matches_glob(arg, argument):
            all_owner_arg_list += [(owner, arg) for owner in owners]

    return all_owner_arg_list


class PermissionRequestException(Exception):
    pass


class RequestAlreadyExists(PermissionRequestException):
    """Trying to create a request for a permission + argument + group which
    already exists in "pending" state."""


class NoOwnersAvailable(PermissionRequestException):
    """No owner was found for the permission + argument combination."""


class RequestAlreadyGranted(PermissionRequestException):
    """Group already has requested permission + argument pair."""


def create_request(
    session: Session, user: User, group: Group, permission: Permission, argument: str, reason: str
) -> PermissionRequest:
    """Creates an permission request and sends notification to the responsible approvers.

    Args:
        session: Database session
        user: User requesting permission
        group: Group requested permission would be applied to
        permission: Permission in question to request
        argument: argument for the given permission
        reason: reason the permission should be granted

    Raises:
        RequestAlreadyExists: Trying to create a request that is already pending
        NoOwnersAvailable: No owner is available for the requested perm + arg.
        grouper.audit.UserNotAuditor: The group has owners that are not auditors
    """
    # check if group already has perm + arg pair
    for _, existing_perm_name, _, existing_perm_argument, _ in group.my_permissions():
        if permission.name == existing_perm_name and argument == existing_perm_argument:
            raise RequestAlreadyGranted()

    # check if request already pending for this perm + arg pair
    existing_count = (
        session.query(PermissionRequest)
        .filter(
            PermissionRequest.group_id == group.id,
            PermissionRequest.permission_id == permission.id,
            PermissionRequest.argument == argument,
            PermissionRequest.status == "pending",
        )
        .count()
    )

    if existing_count > 0:
        raise RequestAlreadyExists()

    # determine owner(s)
    owners_by_arg_by_perm = get_owners_by_grantable_permission(session, separate_global=True)
    owner_arg_list = get_owner_arg_list(
        session, permission, argument, owners_by_arg_by_perm=owners_by_arg_by_perm
    )

    if not owner_arg_list:
        raise NoOwnersAvailable()

    if permission.audited:
        # will raise UserNotAuditor if any owner of the group is not an auditor
        assert_controllers_are_auditors(group)

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
        request=request, user=user, to_status=pending_status, change_at=now
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
        "request_id": request.id,
        "references_header": request.reference_id,
    }

    # TODO: would be nicer if it told you which group you're an approver of
    # that's causing this notification

    mail_to = []
    global_owners = owners_by_arg_by_perm[GLOBAL_OWNERS]["*"]
    non_wildcard_owners = [grant for grant in owner_arg_list if grant[1] != "*"]
    non_global_owners = [grant for grant in owner_arg_list if grant[0] not in global_owners]
    if any(non_wildcard_owners):
        # non-wildcard owners should get all the notifications
        mailto_owner_arg_list = non_wildcard_owners
    elif any(non_global_owners):
        mailto_owner_arg_list = non_global_owners
    else:
        # only the wildcards so they get the notifications
        mailto_owner_arg_list = owner_arg_list

    for owner, arg in mailto_owner_arg_list:
        if owner.email_address:
            mail_to.append(owner.email_address)
        else:
            mail_to.extend([u for t, u in owner.my_members() if t == "User"])

    template_engine = EmailTemplateEngine(settings())
    subject_template = template_engine.get_template("email/pending_permission_request_subj.tmpl")
    subject = subject_template.render(permission=permission.name, group=group.name)
    send_email(
        session, set(mail_to), subject, "pending_permission_request", settings(), email_context
    )

    return request


def get_pending_request_by_group(session: Session, group: Group) -> List[PermissionRequest]:
    """Load pending request for a particular group."""
    return (
        session.query(PermissionRequest)
        .filter(PermissionRequest.status == "pending", PermissionRequest.group_id == group.id)
        .all()
    )


def can_approve_request(
    session: Session,
    request: PermissionRequest,
    owner: User,
    group_ids: Optional[Set[int]] = None,
    owners_by_arg_by_perm: Optional[Dict[object, Dict[str, List[Group]]]] = None,
) -> bool:
    """Determine whether the given owner can approve a permission request.

    Args:
        session: Database session
        request: Pending permission request
        owner: User who may or may not be able to approve the request
        group_ids: If given, the IDs of the groups of which the user is a member (solely so that we
            can avoid another database query if this information is already available)
        owners_by_arg_by_perm: List of permission granters by permission and argument (solely so
            that we can avoid another database query if this information is already available)
    """
    owner_arg_list = get_owner_arg_list(
        session, request.permission, request.argument, owners_by_arg_by_perm
    )
    if group_ids is None:
        group_ids = {g.id for g, _ in get_groups_by_user(session, owner)}

    return bool(group_ids.intersection([o.id for o, arg in owner_arg_list]))


def get_requests(
    session: Session,
    status: str,
    limit: int,
    offset: int,
    owner: Optional[User] = None,
    requester: Optional[User] = None,
    owners_by_arg_by_perm: Optional[Dict[object, Dict[str, List[Group]]]] = None,
) -> Tuple[Requests, int]:
    """Load requests using the given filters.

    Args:
        session: Database session
        status: If not None, filter by particular status
        limit: how many results to return
        offset: the offset into the result set that should be applied
        owner: If not None, filter by requests that the owner can action
        requester: If not None, filter by requests that the requester made
        owners_by_arg_by_perm: List of groups that can grant a given permission, argument pair in
            the format of
            {perm_name: {argument: [group1, group2, ...], ...}, ...}
            This is for convenience/caching if the value has already been fetched.

    Returns:
        2-tuple of (Requests, total) where total is total result size and Requests is the
        data transfer object with requests and associated comments/changes.
    """
    # get all requests
    all_requests = session.query(PermissionRequest)
    if status:
        all_requests = all_requests.filter(PermissionRequest.status == status)
    if requester:
        all_requests = all_requests.filter(PermissionRequest.requester_id == requester.id)

    all_requests = all_requests.order_by(PermissionRequest.requested_at.desc()).all()

    if owners_by_arg_by_perm is None:
        owners_by_arg_by_perm = get_owners_by_grantable_permission(session)

    if owner:
        group_ids = {g.id for g, _ in get_groups_by_user(session, owner)}
        requests = [
            request
            for request in all_requests
            if can_approve_request(
                session,
                request,
                owner,
                group_ids=group_ids,
                owners_by_arg_by_perm=owners_by_arg_by_perm,
            )
        ]
    else:
        requests = all_requests

    total = len(requests)
    requests = requests[offset:limit]

    status_change_by_request_id: Dict[int, List[PermissionRequestStatusChange]] = defaultdict(list)
    if not requests:
        comment_by_status_change_id: Dict[int, Comment] = {}
    else:
        status_changes = (
            session.query(PermissionRequestStatusChange)
            .filter(PermissionRequestStatusChange.request_id.in_([r.id for r in requests]))
            .all()
        )
        for sc in status_changes:
            status_change_by_request_id[sc.request_id].append(sc)

        comments = (
            session.query(Comment)
            .filter(
                Comment.obj_type == OBJ_TYPES_IDX.index("PermissionRequestStatusChange"),
                Comment.obj_pk.in_([s.id for s in status_changes]),
            )
            .all()
        )
        comment_by_status_change_id = {c.obj_pk: c for c in comments}

    return (Requests(requests, status_change_by_request_id, comment_by_status_change_id), total)


def get_request_by_id(session: Session, request_id: int) -> Optional[PermissionRequest]:
    """Get a single request by the request ID."""
    return session.query(PermissionRequest).filter(PermissionRequest.id == request_id).one()


def get_changes_by_request_id(
    session: Session, request_id: int
) -> List[Tuple[PermissionRequestStatusChange, Comment]]:
    status_changes = (
        session.query(PermissionRequestStatusChange)
        .filter(PermissionRequestStatusChange.request_id == request_id)
        .all()
    )

    comments = (
        session.query(Comment)
        .filter(
            Comment.obj_type == OBJ_TYPES_IDX.index("PermissionRequestStatusChange"),
            Comment.obj_pk.in_([s.id for s in status_changes]),
        )
        .all()
    )
    comment_by_status_change_id = {c.obj_pk: c for c in comments}

    return [(sc, comment_by_status_change_id[sc.id]) for sc in status_changes]


def update_request(
    session: Session, request: PermissionRequest, user: User, new_status: str, comment: str
) -> None:
    """Update a request.

    Args:
        session: Database session
        request: Request to update
        user: User making update
        new_status: New status
        comment: Comment to include with status change

    Raises:
        grouper.audit.UserNotAuditor in case we're trying to add an audited permission to a group
            without auditors
    """
    if request.status == new_status:
        # nothing to do
        return

    # make sure the grant can happen
    if new_status == "actioned":
        if request.permission.audited:
            # will raise UserNotAuditor if no auditors are owners of the group
            assert_controllers_are_auditors(request.group)

    # all rows we add have the same timestamp
    now = datetime.utcnow()

    # new status change row
    permission_status_change = PermissionRequestStatusChange(
        request=request,
        user_id=user.id,
        from_status=request.status,
        to_status=new_status,
        change_at=now,
    ).add(session)
    session.flush()

    # new comment
    Comment(
        obj_type=OBJ_TYPES_IDX.index("PermissionRequestStatusChange"),
        obj_pk=permission_status_change.id,
        user_id=user.id,
        comment=comment,
        created_on=now,
    ).add(session)

    # update permissionRequest status
    request.status = new_status
    session.commit()

    if new_status == "actioned":
        # actually grant permission
        try:
            grant_permission(session, request.group.id, request.permission.id, request.argument)
        except IntegrityError:
            session.rollback()

    # audit log
    AuditLog.log(
        session,
        user.id,
        "update_perm_request",
        "updated permission request to status: {}".format(new_status),
        on_group_id=request.group_id,
        on_user_id=request.requester_id,
        on_permission_id=request.permission.id,
    )

    session.commit()

    # send notification

    template_engine = EmailTemplateEngine(settings())
    subject_template = template_engine.get_template("email/pending_permission_request_subj.tmpl")
    subject = "Re: " + subject_template.render(
        permission=request.permission.name, group=request.group.name
    )

    if new_status == "actioned":
        email_template = "permission_request_actioned"
    else:
        email_template = "permission_request_cancelled"

    email_context = {
        "group_name": request.group.name,
        "action_taken_by": user.name,
        "reason": comment,
        "permission_name": request.permission.name,
        "argument": request.argument,
    }

    send_email(
        session, [request.requester.name], subject, email_template, settings(), email_context
    )
