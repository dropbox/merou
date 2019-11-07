from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


@dataclass(order=True, frozen=True)
class Permission:
    name: str
    description: str
    created_on: datetime
    audited: bool
    enabled: bool


@dataclass(frozen=True)
class PermissionAccess:
    """The actions a user can perform on a permission."""

    can_disable: bool
    can_change_audited_status: bool


class PermissionNotFoundException(Exception):
    """Attempt to operate on a permission not found in the storage layer."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Permission {name} not found")
