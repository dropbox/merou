from . import handlers
from ..constants import USER_VALIDATION, GROUP_VALIDATION
HANDLERS = [

    (r"/", handlers.Index),
    (r"/search", handlers.Search),

    (r"/users", handlers.UsersView),

    (r"/groups", handlers.GroupsView),

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
