from . import handlers
from ..constants import (
        NAME_VALIDATION,
        NAME2_VALIDATION,
        USERNAME_VALIDATION,
        PERMISSION_VALIDATION,
        )


HANDLERS = [
    (r"/", handlers.Index),
    (r"/audits", handlers.AuditsView),
    (r"/audits/(?P<audit_id>[0-9]+)/complete", handlers.AuditsComplete),
    (r"/audits/create", handlers.AuditsCreate),
    (r"/groups", handlers.GroupsView),
    (r"/permissions/create", handlers.PermissionsCreate),
    (r"/permissions/{}".format(PERMISSION_VALIDATION), handlers.PermissionView),
    (r"/permissions", handlers.PermissionsView),
    (
        r"/permissions/{}/enable-auditing".format(PERMISSION_VALIDATION),
        handlers.PermissionEnableAuditing
    ),
    (
        r"/permissions/{}/disable-auditing".format(PERMISSION_VALIDATION),
        handlers.PermissionDisableAuditing
    ),
    (r"/permissions/grant/{}".format(NAME_VALIDATION), handlers.PermissionsGrant),
    (
        r"/permissions/{}/revoke/(?P<mapping_id>[0-9]+)".format(PERMISSION_VALIDATION),
        handlers.PermissionsRevoke
    ),
    (r"/search", handlers.Search),
    (r"/users", handlers.UsersView),
    (r"/users/public-keys", handlers.UsersPublicKey),
    (r"/user/requests", handlers.UserRequests),
]

for regex in (r"(?P<user_id>[0-9]+)", USERNAME_VALIDATION):
    HANDLERS.extend([
        (r"/users/{}".format(regex), handlers.UserView),
        (r"/users/{}/disable".format(regex), handlers.UserDisable),
        (r"/users/{}/enable".format(regex), handlers.UserEnable),
        (r"/users/{}/public-key/add".format(regex), handlers.PublicKeyAdd),
        (
            r"/users/{}/public-key/(?P<key_id>[0-9]+)/delete".format(regex),
            handlers.PublicKeyDelete
        ),
    ])

for regex in (r"(?P<group_id>[0-9]+)", NAME_VALIDATION):
    HANDLERS.extend([
        (r"/groups/{}".format(regex), handlers.GroupView),
        (r"/groups/{}/edit".format(regex), handlers.GroupEdit),
        (r"/groups/{}/disable".format(regex), handlers.GroupDisable),
        (r"/groups/{}/enable".format(regex), handlers.GroupEnable),
        (r"/groups/{}/join".format(regex), handlers.GroupJoin),
        (r"/groups/{}/add".format(regex), handlers.GroupAdd),
        (r"/groups/{}/remove".format(regex), handlers.GroupRemove),
        (r"/groups/{}/leave".format(regex), handlers.GroupLeave),
        (r"/groups/{}/requests".format(regex), handlers.GroupRequests),
        (
            r"/groups/{}/requests/(?P<request_id>[0-9]+)".format(regex),
            handlers.GroupRequestUpdate
        ),
        (
            r"/groups/{}/edit/(?P<member_type>user|group)/{}".format(regex, NAME2_VALIDATION),
            handlers.GroupEditMember
        ),
    ])

HANDLERS += [
    (r"/help", handlers.Help),
    (r"/debug/stats", handlers.Stats),
    (r"/debug/profile/(?P<trace_uuid>[\-\w]+)", handlers.PerfProfile),

    (r"/.*", handlers.NotFound),
]
