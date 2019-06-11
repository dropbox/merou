from datetime import datetime
from typing import Dict, List, NamedTuple, Optional

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

# Represents all unique grants of a specific permission (meaning that if a user has the same
# permission and argument granted from multiple groups, it's represented only once).  Contains a
# dictionary of users and service accounts who have been granted that permission, the values in
# which are lists of all the arguments to that permission that they have been granted.
UniqueGrantsOfPermission = NamedTuple(
    "UniqueGrantsOfPermission",
    [("users", Dict[str, List[str]]), ("service_accounts", Dict[str, List[str]])],
)
