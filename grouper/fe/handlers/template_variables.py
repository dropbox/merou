from grouper.constants import USER_METADATA_SHELL_KEY
from grouper.fe.handlers.user_disable import UserDisable
from grouper.fe.handlers.user_enable import UserEnable
from grouper.fe.util import Alert
from grouper.graph import NoSuchGroup, NoSuchUser
from grouper.model_soup import APPROVER_ROLE_INDICIES, AUDIT_STATUS_CHOICES, OWNER_ROLE_INDICES
from grouper.permissions import (get_owner_arg_list, get_pending_request_by_group,
    get_requests_by_owner)
from grouper.public_key import (get_public_key_permissions, get_public_key_tags,
    get_public_keys_of_user)
from grouper.service_account import can_manage_service_account
from grouper.user import (get_log_entries_by_user, user_open_audits, user_requests_aggregate,
    user_role, user_role_index)
from grouper.user_group import get_groups_by_user
from grouper.user_metadata import get_user_metadata_by_key
from grouper.user_password import user_passwords
from grouper.user_permissions import user_grantable_permissions, user_is_user_admin


def get_group_view_template_vars(session, actor, group, graph):
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
    ret["permissions"] = group_md.get('permissions', [])

    ret["permission_requests_pending"] = []
    for req in get_pending_request_by_group(session, group):
        granters = []
        for owner, argument in get_owner_arg_list(session, req.permission, req.argument):
            granters.append(owner.name)
        ret["permission_requests_pending"].append((req, granters))

    ret["audited"] = group_md.get('audited', False)
    ret["log_entries"] = group.my_log_entries()
    ret["num_pending"] = group.my_requests("pending").count()
    ret["current_user_role"] = {
        'is_owner': user_role_index(actor, ret["members"]) in OWNER_ROLE_INDICES,
        'is_approver': user_role_index(actor, ret["members"]) in APPROVER_ROLE_INDICIES,
        'is_manager': user_role(actor, ret["members"]) == "manager",
        'is_member': user_role(actor, ret["members"]) is not None,
        'role': user_role(actor, ret["members"]),
        }
    ret["can_leave"] = (ret["current_user_role"]['is_member'] and not
        ret["current_user_role"]['is_owner'])
    ret["statuses"] = AUDIT_STATUS_CHOICES

    # Add mapping_id to permissions structure
    ret["my_permissions"] = group.my_permissions()
    for perm_up in ret["permissions"]:
        for perm_direct in ret["my_permissions"]:
            if (perm_up['permission'] == perm_direct.name and
                    perm_up['argument'] == perm_direct.argument):
                perm_up['mapping_id'] = perm_direct.mapping_id
                break

    ret["alerts"] = []
    ret["self_pending"] = group.my_requests("pending", user=actor).count()
    if ret["self_pending"]:
        ret["alerts"].append(Alert('info', 'You have a pending request to join this group.',
            None))

    return ret


def get_user_view_template_vars(session, actor, user, graph):
    ret = {}
    ret["can_control"] = (user.name == actor.name or user_is_user_admin(session, actor))
    ret["can_disable"] = UserDisable.check_access(session, actor, user)
    ret["can_enable"] = UserEnable.check_access(session, actor, user)

    if user.id == actor.id:
        ret["num_pending_group_requests"] = user_requests_aggregate(session, actor).count()
        _, ret["num_pending_perm_requests"] = get_requests_by_owner(session, actor,
            status='pending', limit=1, offset=0)
    else:
        ret["num_pending_group_requests"] = None
        ret["num_pending_perm_requests"] = None

    try:
        user_md = graph.get_user_details(user.name)
    except NoSuchUser:
        # Either user is probably very new, so they have no metadata yet, or
        # they're disabled, so we've excluded them from the in-memory graph.
        user_md = {}

    shell = (get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY).data_value
        if get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY)
        else "No shell configured")
    ret["shell"] = shell
    ret["open_audits"] = user_open_audits(session, user)
    group_edge_list = get_groups_by_user(session, user) if user.enabled else []
    ret["groups"] = [{'name': g.name, 'type': 'Group', 'role': ge._role}
        for g, ge in group_edge_list]
    ret["passwords"] = user_passwords(session, user)
    ret["public_keys"] = get_public_keys_of_user(session, user.id)
    for key in ret["public_keys"]:
        key.tags = get_public_key_tags(session, key)
        key.pretty_permissions = ["{} ({})".format(perm.name,
            perm.argument if perm.argument else "unargumented")
            for perm in get_public_key_permissions(session, key)]
    ret["permissions"] = user_md.get('permissions', [])
    ret["log_entries"] = get_log_entries_by_user(session, user)
    ret["user_tokens"] = user.tokens

    return ret


def get_service_account_view_template_vars(session, actor, user, group, graph):
    ret = get_user_view_template_vars(session, actor, user, graph)
    ret.update(get_group_view_template_vars(session, actor, group, graph))
    ret["can_control"] = can_manage_service_account(session, user=actor, tuser=user)
    ret["log_entries"] = sorted(set(get_log_entries_by_user(session, user) +
        group.my_log_entries()), key=lambda x: x.log_time, reverse=True)
    return ret
