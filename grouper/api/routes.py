from .handlers import Users, Groups, Stats, NotFound
from ..constants import USER_VALIDATION, GROUP_VALIDATION

HANDLERS = [

    (r"/users", Users),
    (r"/users/{}".format(USER_VALIDATION), Users),

    (r"/groups", Groups),
    (r"/groups/{}".format(GROUP_VALIDATION), Groups),

    (r"/debug/stats", Stats),

    (r"/.*", NotFound),

]
