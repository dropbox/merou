from datetime import datetime
from typing import TYPE_CHECKING

from grouper.constants import USER_METADATA_GITHUB_USERNAME_KEY, USER_METADATA_SHELL_KEY
from grouper.entities.group_edge import APPROVER_ROLE_INDICES, OWNER_ROLE_INDICES
from grouper.fe.alerts import Alert
from grouper.fe.settings import settings
from grouper.graph import NoSuchGroup, NoSuchUser
from grouper.group_requests import count_requests_by_group
from grouper.group_service_account import get_service_accounts
from grouper.models.audit_member import AUDIT_STATUS_CHOICES
from grouper.permissions import get_owner_arg_list, get_pending_request_by_group, get_requests
from grouper.public_key import get_public_keys_of_user
from grouper.role_user import can_manage_role_user
from grouper.service_account import can_manage_service_account, service_account_permissions
from grouper.user import (
    get_log_entries_by_user,
    user_open_audits,
    user_requests_aggregate,
    user_role,
    user_role_index,
)
from grouper.user_group import get_groups_by_user
from grouper.user_metadata import get_user_metadata, get_user_metadata_by_key
from grouper.user_password import user_passwords
from grouper.user_permissions import user_grantable_permissions, user_is_user_admin

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.models.base.session import Session
    from grouper.models.group import Group
    from grouper.models.user import User
    from typing import Any, Dict


def get_group_view_template_vars(session, actor, group, graph):
    # type: (Session, User, Group, GroupGraph) -> Dict[str, Any]
    ret = {}
    ret["grantable"] = user_grantable_permissions(session, actor)

    try:
        group_md = graph.get_group_details(group.name)
    except NoSuchGroup:
        # Very new group with no metadata yet, or it has been disabled and
        # excluded from in-memory cache.
        group_md = {}

    ret["members"] = group.my_members()
    ret["groups"] = group.my_groups()
    ret["service_accounts"] = get_service_accounts(session, group)
    ret["permissions"] = group_md.get("permissions", [])
    for permission in ret["permissions"]:
        permission["granted_on"] = datetime.fromtimestamp(permission["granted_on"])

    ret["permission_requests_pending"] = []
    for req in get_pending_request_by_group(session, group):
        granters = []
        for owner, argument in get_owner_arg_list(session, req.permission, req.argument):
            granters.append(owner.name)
        ret["permission_requests_pending"].append((req, granters))

    ret["audited"] = group_md.get("audited", False)
    ret["log_entries"] = group.my_log_entries()
    ret["num_pending"] = count_requests_by_group(session, group, status="pending")
    ret["current_user_role"] = {
        "is_owner": user_role_index(actor, ret["members"]) in OWNER_ROLE_INDICES,
        "is_approver": user_role_index(actor, ret["members"]) in APPROVER_ROLE_INDICES,
        "is_manager": user_role(actor, ret["members"]) == "manager",
        "is_member": user_role(actor, ret["members"]) is not None,
        "role": user_role(actor, ret["members"]),
    }
    ret["statuses"] = AUDIT_STATUS_CHOICES

    # The user can leave if they're a normal member, or if they're not the only owner.
    number_of_owners = len(
        [m for (t, m), o in ret["members"].items() if t == "User" and o.role in OWNER_ROLE_INDICES]
    )
    ret["can_leave"] = ret["current_user_role"]["is_member"] and (
        not ret["current_user_role"]["is_owner"] or number_of_owners > 1
    )

    # Add mapping_id to permissions structure
    ret["my_permissions"] = group.my_permissions()
    for perm_up in ret["permissions"]:
        for perm_direct in ret["my_permissions"]:
            if (
                perm_up["permission"] == perm_direct.name
                and perm_up["argument"] == perm_direct.argument
            ):
                perm_up["mapping_id"] = perm_direct.mapping_id
                break

    ret["alerts"] = []
    ret["self_pending"] = count_requests_by_group(session, group, status="pending", user=actor)
    if ret["self_pending"]:
        ret["alerts"].append(Alert("info", "You have a pending request to join this group.", None))

    return ret


def get_user_view_template_vars(session, actor, user, graph):
    # type: (Session, User, User, GroupGraph) -> Dict[str, Any]
    # TODO(cbguder): get around circular dependencies
    from grouper.fe.handlers.user_disable import UserDisable
    from grouper.fe.handlers.user_enable import UserEnable

    ret = {}  # type: Dict[str, Any]
    if user.is_service_account:
        ret["can_control"] = can_manage_service_account(
            session, user.service_account, actor
        ) or user_is_user_admin(session, actor)
        ret["can_disable"] = ret["can_control"]
        ret["can_enable"] = user_is_user_admin(session, actor)
        ret["can_enable_preserving_membership"] = user_is_user_admin(session, actor)
        ret["account"] = user.service_account
    else:
        ret["can_control"] = user.name == actor.name or user_is_user_admin(session, actor)
        ret["can_disable"] = UserDisable.check_access(session, actor, user)
        ret["can_enable_preserving_membership"] = UserEnable.check_access(session, actor, user)
        ret["can_enable"] = UserEnable.check_access_without_membership(session, actor, user)

    if user.id == actor.id:
        ret["num_pending_group_requests"] = user_requests_aggregate(session, actor).count()
        _, ret["num_pending_perm_requests"] = get_requests(
            session, status="pending", limit=1, offset=0, owner=actor
        )
    else:
        ret["num_pending_group_requests"] = None
        ret["num_pending_perm_requests"] = None

    try:
        user_md = graph.get_user_details(user.name)
    except NoSuchUser:
        # Either user is probably very new, so they have no metadata yet, or
        # they're disabled, so we've excluded them from the in-memory graph.
        user_md = {}

    shell_metadata = get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY)
    ret["shell"] = shell_metadata.data_value if shell_metadata else "No shell configured"
    github_username = get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY)
    ret["github_username"] = github_username.data_value if github_username else "(Unset)"
    addl_metadata = get_user_metadata(
        session, user.id, exclude=[USER_METADATA_SHELL_KEY, USER_METADATA_GITHUB_USERNAME_KEY]
    )

    ret["addl_metadata"] = addl_metadata if addl_metadata else []

    known_metadata_fields = set(settings().metadata_options.keys())
    set_metadata_fields = {md.data_key for md in addl_metadata}

    ret["unset_metadata"] = known_metadata_fields - set_metadata_fields

    ret["open_audits"] = user_open_audits(session, user)
    group_edge_list = get_groups_by_user(session, user) if user.enabled else []
    ret["groups"] = [
        {"name": g.name, "type": "Group", "role": ge._role} for g, ge in group_edge_list
    ]
    ret["passwords"] = user_passwords(session, user)
    ret["public_keys"] = get_public_keys_of_user(session, user.id)
    ret["log_entries"] = get_log_entries_by_user(session, user)
    ret["user_tokens"] = user.tokens

    if user.is_service_account:
        service_account = user.service_account
        ret["permissions"] = service_account_permissions(session, service_account)
    else:
        ret["permissions"] = user_md.get("permissions", [])
        for permission in ret["permissions"]:
            permission["granted_on"] = datetime.fromtimestamp(permission["granted_on"])

    return ret


def get_role_user_view_template_vars(session, actor, user, group, graph):
    # type: (Session, User, User, Group, GroupGraph) -> Dict[str, Any]
    ret = get_user_view_template_vars(session, actor, user, graph)
    ret.update(get_group_view_template_vars(session, actor, group, graph))
    ret["can_control"] = can_manage_role_user(session, user=actor, tuser=user)
    ret["log_entries"] = sorted(
        set(get_log_entries_by_user(session, user) + group.my_log_entries()),
        key=lambda x: x.log_time,
        reverse=True,
    )
    return ret
