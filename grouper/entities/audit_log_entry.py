from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional


@dataclass(frozen=True)
class AuditLogEntry:
    date: datetime
    actor: str
    action: str
    description: str
    on_user: Optional[str]
    on_group: Optional[str]
    on_permission: Optional[str]
