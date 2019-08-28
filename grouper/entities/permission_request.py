from enum import Enum
from typing import List, NamedTuple

from grouper.entities.permission_grant import GrantablePermission


class PermissionRequestStatus(Enum):
    PENDING = "pending"
    ACTIONED = "actioned"
    CANCELLED = "cancelled"


PermissionRequest = NamedTuple(
    "PermissionRequest",
    [
        ("group", str),  # Name of the group for which this permission is requested
        ("grant", GrantablePermission),
        ("status", PermissionRequestStatus),
    ],
)

# Information about a permission grant request, including names of groups that can approve the
# request
PermissionRequestWithApprovers = NamedTuple(
    "PermissionRequestWithApprovers",
    [
        ("group", str),  # Name of the group for which this permission is requested
        ("grant", GrantablePermission),
        ("status", PermissionRequestStatus),
        ("approver_groups", List[str]),
    ],
)
