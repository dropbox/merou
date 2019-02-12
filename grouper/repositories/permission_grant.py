from typing import TYPE_CHECKING

from grouper.entities.permission_grant import PermissionGrant
from grouper.repositories.interfaces import PermissionGrantRepository

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from typing import List


class GraphPermissionGrantRepository(PermissionGrantRepository):
    """Graph-aware storage layer for permission grants."""

    def __init__(self, graph):
        # type: (GroupGraph) -> None
        self.graph = graph

    def permissions_for_user(self, user):
        # type: (str) -> List[PermissionGrant]
        user_details = self.graph.get_user_details(user)
        permissions = []
        for permission_data in user_details["permissions"]:
            permission = PermissionGrant(
                name=permission_data["permission"], argument=permission_data["argument"]
            )
            permissions.append(permission)
        return permissions

    def user_has_permission(self, user, permission):
        # type: (str, str) -> bool
        for user_permission in self.permissions_for_user(user):
            if permission == user_permission.name:
                return True
        return False
