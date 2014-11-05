from . import handlers
from ..constants import USER_VALIDATION, GROUP_VALIDATION, PERMISSION_VALIDATION

HANDLERS = [
    (r"/", handlers.Index),
    (r"/groups", handlers.GroupsView),
    (r"/permission/{}".format(PERMISSION_VALIDATION), handlers.PermissionView),
    (r"/permissions", handlers.PermissionsView),
    (r"/permissions/create", handlers.PermissionsCreate),
    (r"/permissions/grant/{}".format(GROUP_VALIDATION), handlers.PermissionsGrant),
    (
        r"/permissions/{}/revoke/(?P<mapping_id>[0-9+])".format(PERMISSION_VALIDATION),
        handlers.PermissionsRevoke
    ),
    (r"/search", handlers.Search),
    (r"/users", handlers.UsersView),
]

for regex in (r"(?P<user_id>[0-9]+)", USER_VALIDATION):
    HANDLERS.extend([
        (r"/users/{}".format(regex), handlers.UserView),
        (r"/users/{}/disable".format(regex), handlers.UserDisable),
        (r"/users/{}/enable".format(regex), handlers.UserEnable),
        (r"/users/{}/public-key/add".format(regex), handlers.PublicKeyAdd),
        (
            r"/users/{}/public-key/(?P<key_id>[0-9+])/delete".format(regex),
            handlers.PublicKeyDelete
        ),
    ])

for regex in (r"(?P<group_id>[0-9]+)", GROUP_VALIDATION):
    HANDLERS.extend([
        (r"/groups/{}".format(regex), handlers.GroupView),
        (r"/groups/{}/edit".format(regex), handlers.GroupEdit),
        (r"/groups/{}/disable".format(regex), handlers.GroupDisable),
        (r"/groups/{}/enable".format(regex), handlers.GroupEnable),
        (r"/groups/{}/join".format(regex), handlers.GroupJoin),
        (r"/groups/{}/requests".format(regex), handlers.GroupRequests),
        (
            r"/groups/{}/requests/(?P<request_id>[0-9]+)".format(regex),
            handlers.GroupRequestUpdate
        ),
    ])

HANDLERS += [
    (r"/help", handlers.Help),
    (r"/debug/stats", handlers.Stats),

    (r"/.*", handlers.NotFound),
]
