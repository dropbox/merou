from datetime import datetime
from typing import NamedTuple, Optional

GroupPermissionGrant = NamedTuple(
    "GroupPermissionGrant",
    [
        ("group", str),
        ("permission", str),
        ("argument", str),
        ("granted_on", datetime),
        ("is_alias", bool),
        ("grant_id", Optional[int]),
    ],
)
ServiceAccountPermissionGrant = NamedTuple(
    "ServiceAccountPermissionGrant",
    [
        ("service_account", str),
        ("permission", str),
        ("argument", str),
        ("granted_on", datetime),
        ("is_alias", bool),
        ("grant_id", Optional[int]),
    ],
)
