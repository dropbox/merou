from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime
    from typing import Dict, List, Optional


@dataclass(order=True, frozen=True)
class GroupPermissionGrant:
    group: str
    permission: str
    argument: str
    granted_on: datetime
    is_alias: bool
    grant_id: Optional[int] = None


@dataclass(order=True, frozen=True)
class ServiceAccountPermissionGrant:
    service_account: str
    permission: str
    argument: str
    granted_on: datetime
    is_alias: bool
    grant_id: Optional[int] = None


@dataclass(frozen=True)
class UniqueGrantsOfPermission:
    """Unique grants of a given permission.

    A unique grant means that if a user has the same permission and argument granted from multiple
    groups, it's represented only once.  Contains a dictionary of users, role users, and service
    accounts who have been granted that permission, the values in which are lists of all the
    arguments to that permission that they have been granted.
    """

    users: Dict[str, List[str]]
    role_users: Dict[str, List[str]]
    service_accounts: Dict[str, List[str]]
