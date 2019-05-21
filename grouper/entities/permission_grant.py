from datetime import datetime
from typing import NamedTuple

# Represents a grant of a permission to either a group or a service account.
PermissionGrant = NamedTuple(
    "PermissionGrant",
    [("permission", str), ("argument", str), ("granted_on", datetime), ("is_alias", bool)],
)
GroupPermissionGrant = NamedTuple(
    "GroupPermissionGrant", [("group", str), ("permission", str), ("argument", str)]
)
ServiceAccountPermissionGrant = NamedTuple(
    "ServiceAccountPermissionGrant",
    [("service_account", str), ("permission", str), ("argument", str)],
)
