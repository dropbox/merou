"""Routes and handlers for the Grouper API server.

Provides the variable HANDLERS, which contains tuples of route regexes and handlers.  Do not
provide additional handler arguments as a third argument of the tuple.  A standard set of
additional arguments will be injected when the Tornado Application object is created.
"""

from grouper.api.handlers import (
    Groups,
    MultiUsers,
    NotFound,
    Permissions,
    ServiceAccounts,
    TokenValidate,
    Users,
    UsersPublicKeys,
)
from grouper.constants import NAME_VALIDATION, PERMISSION_VALIDATION
from grouper.handlers.health_check import HealthCheck

HANDLERS = [
    (r"/users", Users),
    (r"/users/{}".format(NAME_VALIDATION), Users),
    (r"/token/validate".format(NAME_VALIDATION), TokenValidate),
    (r"/public-keys", UsersPublicKeys),
    (r"/groups", Groups),
    (r"/groups/{}".format(NAME_VALIDATION), Groups),
    (r"/permissions", Permissions),
    (r"/permissions/{}".format(PERMISSION_VALIDATION), Permissions),
    (r"/service_accounts", ServiceAccounts),
    (r"/service_accounts/{}".format(NAME_VALIDATION), ServiceAccounts),
    (r"/multi/users", MultiUsers),
    (r"/debug/health", HealthCheck),
    (r"/.*", NotFound),
]
