from grouper.api.handlers import (
        Groups,
        NotFound,
        Permissions,
        ServiceAccounts,
        TokenValidate,
        Users,
        UsersPublicKeys,
        )
from grouper.constants import DEBUG_ROUTE_PATH, NAME_VALIDATION, PERMISSION_VALIDATION
from grouper.handlers.stats import Stats

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

    (DEBUG_ROUTE_PATH, Stats),

    (r"/.*", NotFound),

]
