from .handlers import Users, UsersPublicKeys, Groups, Permissions, Stats, NotFound, TokenValidate
from ..constants import NAME_VALIDATION, PERMISSION_VALIDATION

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
