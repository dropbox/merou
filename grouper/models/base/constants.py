from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Dict, Set


REQUEST_STATUS_CHOICES: Dict[str, Set[str]] = {
    # Request has been made and awaiting action.
    "pending": set(["actioned", "cancelled"]),
    "actioned": set([]),
    "cancelled": set([]),
}

OBJ_TYPES_IDX = (
    "User",
    "Group",
    "Request",
    "RequestStatusChange",
    "PermissionRequestStatusChange",
    "ServiceAccount",
)
OBJ_TYPES = {obj_type: idx for idx, obj_type in enumerate(OBJ_TYPES_IDX)}
