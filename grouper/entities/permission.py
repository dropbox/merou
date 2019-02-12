from typing import NamedTuple

Permission = NamedTuple("Permission", [("name", str), ("enabled", bool)])


class PermissionNotFoundException(Exception):
    """Attempt to operate on a permission not found in the storage layer."""

    def __init__(self, name):
        # type: (str) -> None
        msg = "Permission {} not found".format(name)
        super(PermissionNotFoundException, self).__init__(msg)
