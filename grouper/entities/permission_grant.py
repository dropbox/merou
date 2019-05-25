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

# Represents all grants of a specific permission, as a dictionary of users and service accounts who
# have been granted that permission to lists of all the arguments to that permission that they have
# been granted.
AllGrantsOfPermission = NamedTuple(
    "AllGrantsOfPermission",
    [("users", Dict[str, List[str]]), ("service_accounts", Dict[str, List[str]])],
)

# The same, but for every permission, stored in a dictionary mapping permission names to those
# grants.
AllGrants = Dict[str, AllGrantsOfPermission]
