from datetime import datetime
from typing import NamedTuple

# Represents a grant of a permission to either a group or a service account.
PermissionGrant = NamedTuple(
    "PermissionGrant",
    [("permission", str), ("argument", str), ("granted_on", datetime), ("is_alias", bool)],
)

# Variations used when the target of the grant is not obvious in context and needs to be included
# in the returned data (such as when listing all grants of a given permission to both groups and
# service accounts), or when the specific permission grant needs to be referred to later (such as
# for revocation) and thus needs a unique ID.
GroupPermissionGrant = NamedTuple(
    "GroupPermissionGrant",
    [
        ("group", str),
        ("permission", str),
        ("argument", str),
        ("granted_on", datetime),
        ("mapping_id", int),
    ],
)
ServiceAccountPermissionGrant = NamedTuple(
    "ServiceAccountPermissionGrant",
    [
        ("service_account", str),
        ("permission", str),
        ("argument", str),
        ("granted_on", datetime),
        ("mapping_id", int),
    ],
)
