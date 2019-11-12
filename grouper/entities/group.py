from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from grouper.constants import NAME_VALIDATION

if TYPE_CHECKING:
    from typing import Optional


class GroupJoinPolicy(Enum):
    CAN_JOIN = "canjoin"
    CAN_ASK = "canask"
    NOBODY = "nobody"


@dataclass(frozen=True)
class Group:
    name: str
    description: str
    email_address: Optional[str]
    join_policy: GroupJoinPolicy
    enabled: bool
    is_role_user: bool


class GroupNotFoundException(Exception):
    """Attempt to operate on a group not found in the storage layer."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Group {name} not found")


class InvalidGroupNameException(Exception):
    """A group name does not match the validation regex."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Group name {name} does not match validation regex {NAME_VALIDATION}")
