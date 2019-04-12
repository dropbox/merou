from typing import NamedTuple

PermissionGrant = NamedTuple("PermissionGrant", [("name", str), ("argument", str)])
GroupPermissionGrant = NamedTuple(
    "GroupPermissionGrant", [("group", str), ("permission", str), ("argument", str)]
)
ServiceAccountPermissionGrant = NamedTuple(
    "ServiceAccountPermissionGrant",
    [("service_account", str), ("permission", str), ("argument", str)],
)
