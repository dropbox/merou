from grouper.constants import (
        NAME_VALIDATION,
        NAME2_VALIDATION,
        PERMISSION_VALIDATION,
        USERNAME_VALIDATION,
        )
from grouper.fe import handlers
import grouper.fe.handlers.index
import grouper.fe.handlers.search
import grouper.fe.handlers.user_view
import grouper.fe.handlers.permissions_create
import grouper.fe.handlers.permission_disable_auditing
import grouper.fe.handlers.permission_enable_auditing
import grouper.fe.handlers.permissions_grant
import grouper.fe.handlers.permissions_revoke
import grouper.fe.handlers.permissions_view
import grouper.fe.handlers.permission_view
import grouper.fe.handlers.users_view
import grouper.fe.handlers.users_public_key
import grouper.fe.handlers.users_user_tokens
import grouper.fe.handlers.user_enable
import grouper.fe.handlers.user_disable
import grouper.fe.handlers.user_requests
import grouper.fe.handlers.group_view
import grouper.fe.handlers.group_edit_member
import grouper.fe.handlers.group_request_update
import grouper.fe.handlers.group_requests
import grouper.fe.handlers.group_permission_request
import grouper.fe.handlers.permissions_requests
import grouper.fe.handlers.permissions_request_update
import grouper.fe.handlers.audits_complete
import grouper.fe.handlers.audits_create
import grouper.fe.handlers.audits_view
import grouper.fe.handlers.groups_view
import grouper.fe.handlers.group_add
import grouper.fe.handlers.group_remove
import grouper.fe.handlers.group_join
import grouper.fe.handlers.group_leave
import grouper.fe.handlers.group_edit
import grouper.fe.handlers.group_enable
import grouper.fe.handlers.group_disable
import grouper.fe.handlers.public_key_add
import grouper.fe.handlers.public_key_delete
import grouper.fe.handlers.help
import grouper.fe.handlers.not_found
import grouper.fe.handlers.user_token_add
import grouper.fe.handlers.user_token_disable
import grouper.fe.handlers.stats
import grouper.fe.handlers.perf_profile


HANDLERS = [
    (r"/", grouper.fe.handlers.index.Index),
    (r"/audits", grouper.fe.handlers.audits_view.AuditsView),
    (r"/audits/(?P<audit_id>[0-9]+)/complete", grouper.fe.handlers.audits_complete.AuditsComplete),
    (r"/audits/create", grouper.fe.handlers.audits_create.AuditsCreate),
    (r"/groups", grouper.fe.handlers.groups_view.GroupsView),
    (r"/permissions/create", grouper.fe.handlers.permissions_create.PermissionsCreate),
    (r"/permissions/requests", grouper.fe.handlers.permissions_requests.PermissionsRequests),
    (r"/permissions/requests/(?P<request_id>[0-9]+)", grouper.fe.handlers.permissions_request_update.PermissionsRequestUpdate),
    (r"/permissions/{}".format(PERMISSION_VALIDATION), grouper.fe.handlers.permission_view.PermissionView),
    (r"/permissions", grouper.fe.handlers.permissions_view.PermissionsView),
    (
        r"/permissions/{}/enable-auditing".format(PERMISSION_VALIDATION),
        grouper.fe.handlers.permission_enable_auditing.PermissionEnableAuditing
    ),
    (
        r"/permissions/{}/disable-auditing".format(PERMISSION_VALIDATION),
        grouper.fe.handlers.permission_disable_auditing.PermissionDisableAuditing
    ),
    (r"/permissions/grant/{}".format(NAME_VALIDATION), grouper.fe.handlers.permissions_grant.PermissionsGrant),
    (
        r"/permissions/{}/revoke/(?P<mapping_id>[0-9]+)".format(PERMISSION_VALIDATION),
        grouper.fe.handlers.permissions_revoke.PermissionsRevoke
    ),
    (r"/search", grouper.fe.handlers.search.Search),
    (r"/users", grouper.fe.handlers.users_view.UsersView),
    (r"/users/public-keys", grouper.fe.handlers.users_public_key.UsersPublicKey),
    (r"/users/tokens", grouper.fe.handlers.users_user_tokens.UsersUserTokens),
    (r"/user/requests", grouper.fe.handlers.user_requests.UserRequests),
]

for regex in (r"(?P<user_id>[0-9]+)", USERNAME_VALIDATION):
    HANDLERS.extend([
        (r"/users/{}".format(regex), grouper.fe.handlers.user_view.UserView),
        (r"/users/{}/disable".format(regex), grouper.fe.handlers.user_disable.UserDisable),
        (r"/users/{}/enable".format(regex), grouper.fe.handlers.user_enable.UserEnable),
        (r"/users/{}/public-key/add".format(regex), grouper.fe.handlers.public_key_add.PublicKeyAdd),
        (
            r"/users/{}/public-key/(?P<key_id>[0-9]+)/delete".format(regex),
            grouper.fe.handlers.public_key_delete.PublicKeyDelete
        ),
        (r"/users/{}/tokens/add".format(regex), grouper.fe.handlers.user_token_add.UserTokenAdd),
        (r"/users/{}/tokens/(?P<token_id>[0-9]+)/disable".format(regex), grouper.fe.handlers.user_token_disable.UserTokenDisable),
    ])

for regex in (r"(?P<group_id>[0-9]+)", NAME_VALIDATION):
    HANDLERS.extend([
        (r"/groups/{}".format(regex), grouper.fe.handlers.group_view.GroupView),
        (r"/groups/{}/edit".format(regex), grouper.fe.handlers.group_edit.GroupEdit),
        (r"/groups/{}/disable".format(regex), grouper.fe.handlers.group_disable.GroupDisable),
        (r"/groups/{}/enable".format(regex), grouper.fe.handlers.group_enable.GroupEnable),
        (r"/groups/{}/join".format(regex), grouper.fe.handlers.group_join.GroupJoin),
        (r"/groups/{}/add".format(regex), grouper.fe.handlers.group_add.GroupAdd),
        (r"/groups/{}/remove".format(regex), grouper.fe.handlers.group_remove.GroupRemove),
        (r"/groups/{}/leave".format(regex), grouper.fe.handlers.group_leave.GroupLeave),
        (r"/groups/{}/requests".format(regex), grouper.fe.handlers.group_requests.GroupRequests),
        (
            r"/groups/{}/requests/(?P<request_id>[0-9]+)".format(regex),
            grouper.fe.handlers.group_request_update.GroupRequestUpdate
        ),
        (r"/groups/{}/permission/request".format(regex), grouper.fe.handlers.group_permission_request.GroupPermissionRequest),
        (
            r"/groups/{}/edit/(?P<member_type>user|group)/{}".format(regex, NAME2_VALIDATION),
            grouper.fe.handlers.group_edit_member.GroupEditMember
        ),
    ])

HANDLERS += [
    (r"/help", grouper.fe.handlers.help.Help),
    (r"/debug/stats", grouper.fe.handlers.stats.Stats),
    (r"/debug/profile/(?P<trace_uuid>[\-\w]+)", grouper.fe.handlers.perf_profile.PerfProfile),

    (r"/.*", grouper.fe.handlers.not_found.NotFound),
]
