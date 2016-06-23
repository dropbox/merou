from grouper.api.handlers import (
        Groups,
        NotFound,
        Permissions,
        TokenValidate,
        Users,
        UsersPublicKeys,
        )
from grouper.constants import NAME_VALIDATION, PERMISSION_VALIDATION
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

    (r"/debug/stats", Stats),

    (r"/.*", NotFound),

]
