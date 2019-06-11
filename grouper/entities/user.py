from typing import List, NamedTuple

# A single public key for a user.
PublicKey = NamedTuple(
    "PublicKey", [("public_key", str), ("fingerprint", str), ("fingerprint_sha256", str)]
)

# A single key/value pair stored as user metadata.
UserMetadata = NamedTuple("UserMetadata", [("key", str), ("value", str)])

# Details for a single non-service-account user.
User = NamedTuple(
    "User",
    [
        ("name", str),
        ("enabled", bool),
        ("role_user", bool),
        ("metadata", List[UserMetadata]),
        ("public_keys", List[PublicKey]),
    ],
)


class UserNotFoundException(Exception):
    """Attempt to operate on a user not found in the storage layer."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "User {} not found".format(name)
        super(UserNotFoundException, self).__init__(msg)


class UserIsEnabledException(Exception):
    """Operation failed because user is a member of groups."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "User {} is enabled".format(name)
        super(UserIsEnabledException, self).__init__(msg)


class UserIsMemberOfGroupsException(Exception):
    """Operation failed because user is a member of groups."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "User {} is a member of one or more groups".format(name)
        super(UserIsMemberOfGroupsException, self).__init__(msg)


class UserHasPendingRequestsException(Exception):
    """Operation failed because user has pending requests."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "User {} has one or more pending requests".format(name)
        super(UserHasPendingRequestsException, self).__init__(msg)
