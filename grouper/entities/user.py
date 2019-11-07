from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List


@dataclass(frozen=True)
class PublicKey:
    public_key: str
    fingerprint: str
    fingerprint_sha256: str


@dataclass(frozen=True)
class UserMetadata:
    key: str
    value: str


@dataclass(frozen=True)
class User:
    name: str
    enabled: bool
    role_user: bool
    metadata: List[UserMetadata]
    public_keys: List[PublicKey]


class UserNotFoundException(Exception):
    """Attempt to operate on a user not found in the storage layer."""

    def __init__(self, name: str) -> None:
        super().__init__(f"User {name} not found")


class UserIsEnabledException(Exception):
    """Operation failed because user is not disabled."""

    def __init__(self, name: str) -> None:
        super().__init__(f"User {name} is enabled")


class UserIsMemberOfGroupsException(Exception):
    """Operation failed because user is a member of groups."""

    def __init__(self, name: str) -> None:
        super().__init__(f"User {name} is a member of one or more groups")


class UserHasPendingRequestsException(Exception):
    """Operation failed because user has pending requests."""

    def __init__(self, name: str) -> None:
        super().__init__(f"User {name} has one or more pending requests")
