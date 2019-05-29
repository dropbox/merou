from enum import Enum
from typing import NamedTuple, Optional

from grouper.constants import NAME_VALIDATION


class GroupJoinPolicy(Enum):
    CAN_JOIN = "canjoin"
    CAN_ASK = "canask"
    NOBODY = "nobody"


Group = NamedTuple(
    "Group",
    [
        ("name", str),
        ("description", str),
        ("email_address", Optional[str]),
        ("join_policy", GroupJoinPolicy),
        ("enabled", bool),
        ("is_role_user", bool),
    ],
)


class GroupNotFoundException(Exception):
    """Attempt to operate on a group not found in the storage layer."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "Group {} not found".format(name)
        super(GroupNotFoundException, self).__init__(msg)


class InvalidGroupNameException(Exception):
    """A group name does not match the validation regex."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "Group name {} does not match validation regex {}".format(name, NAME_VALIDATION)
        super(InvalidGroupNameException, self).__init__(msg)
