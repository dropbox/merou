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
