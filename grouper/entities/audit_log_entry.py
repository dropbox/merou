from datetime import datetime
from typing import NamedTuple, Optional

AuditLogEntry = NamedTuple(
    "AuditLogEntry",
    [
        ("date", datetime),
        ("actor", str),
        ("action", str),
        ("description", str),
        ("on_user", Optional[str]),
        ("on_group", Optional[str]),
        ("on_permission", Optional[str]),
    ],
)
