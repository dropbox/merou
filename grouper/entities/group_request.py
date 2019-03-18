from enum import Enum
from typing import NamedTuple


class GroupRequestStatus(Enum):
    PENDING = "pending"
    ACTIONED = "actioned"
    CANCELLED = "cancelled"


UserGroupRequest = NamedTuple(
    "GroupRequest",
    [
        ("id", int),
        ("user", str),
        ("group", str),
        ("requester", str),
        ("status", GroupRequestStatus),
    ],
)


class UserGroupRequestNotFoundException(Exception):
    """Attempt to operate on a UserGroupRequest not found in the storage layer."""

    def __init__(self, request):
        # type: (UserGroupRequest) -> None
        msg = "Group membership request {} not found".format(request.id)
        super(UserGroupRequestNotFoundException, self).__init__(msg)
