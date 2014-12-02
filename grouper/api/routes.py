from .handlers import Users, Groups, Permissions, Stats, NotFound
from ..constants import USER_VALIDATION, GROUP_VALIDATION, PERMISSION_VALIDATION

HANDLERS = [

    (r"/users", Users),
    (r"/users/{}".format(USER_VALIDATION), Users),

    (r"/groups", Groups),
    (r"/groups/{}".format(GROUP_VALIDATION), Groups),

    (r"/permissions", Permissions),
    (r"/permissions/{}".format(PERMISSION_VALIDATION), Permissions),

    (r"/debug/stats", Stats),

    (r"/.*", NotFound),

]
