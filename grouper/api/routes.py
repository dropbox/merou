"""Routes and handlers for the Grouper API server.

Provides the variable HANDLERS, which contains tuples of route regexes and handlers.  Do not
provide additional handler arguments as a third argument of the tuple.  A standard set of
additional arguments will be injected when the Tornado Application object is created.
"""

from grouper.api.handlers import (
    Grants,
    Groups,
    MultiUsers,
    NotFound,
    Permissions,
    ServiceAccounts,
    TokenValidate,
    UserMetadata,
    Users,
    UsersPublicKeys,
)
from grouper.constants import NAME_VALIDATION, PERMISSION_VALIDATION
from grouper.handlers.health_check import HealthCheck

HANDLERS = [
    ("/debug/health", HealthCheck),
    ("/grants", Grants),
    (f"/grants/{PERMISSION_VALIDATION}", Grants),
    ("/groups", Groups),
    (f"/groups/{NAME_VALIDATION}", Groups),
    ("/permissions", Permissions),
    (f"/permissions/{PERMISSION_VALIDATION}", Permissions),
    ("/public-keys", UsersPublicKeys),
    ("/service_accounts", ServiceAccounts),
    (f"/service_accounts/{NAME_VALIDATION}", ServiceAccounts),
    ("/user-metadata", UserMetadata),
    ("/users", Users),
    (f"/users/{NAME_VALIDATION}", Users),
    ("/multi/users", MultiUsers),
    ("/token/validate", TokenValidate),
    ("/.*", NotFound),
]
