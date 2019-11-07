from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GroupRequestStatus(Enum):
    PENDING = "pending"
    ACTIONED = "actioned"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class UserGroupRequest:
    id: int
    user: str
    group: str
    requester: str
    status: GroupRequestStatus


class UserGroupRequestNotFoundException(Exception):
    """Attempt to operate on a UserGroupRequest not found in the storage layer."""

    def __init__(self, request: UserGroupRequest) -> None:
        super().__init__(f"Group membership request {request.id} not found")
