from datetime import datetime
from typing import NamedTuple

Permission = NamedTuple(
    "Permission",
    [
        ("name", str),
        ("description", str),
        ("created_on", datetime),
        ("audited", bool),
        ("enabled", bool),
    ],
)

# The actions a user can perform on a permission.
PermissionAccess = NamedTuple(
    "PermissionAccess", [("can_disable", bool), ("can_change_audited_status", bool)]
)


class PermissionNotFoundException(Exception):
    """Attempt to operate on a permission not found in the storage layer."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "Permission {} not found".format(name)
        super().__init__(msg)
