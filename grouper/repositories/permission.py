from typing import TYPE_CHECKING

from grouper.entities.permission import Permission, PermissionNotFoundException
from grouper.models.counter import Counter
from grouper.models.permission import Permission as SQLPermission

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Optional


class PermissionRepository(object):
    """Storage layer for permissions."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def get_permission(self, name):
        # type: (str) -> Optional[Permission]
        permission = SQLPermission.get(self.session, name=name)
        if not permission:
            return None
        return Permission(name=permission.name, enabled=permission.enabled)

    def disable_permission(self, name):
        # type: (str) -> None
        permission = SQLPermission.get(self.session, name=name)
        if not permission:
            raise PermissionNotFoundException(name)
        permission.enabled = False
        Counter.incr(self.session, "updates")
