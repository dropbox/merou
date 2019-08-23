from typing import TYPE_CHECKING

from sqlalchemy.sql import label

from grouper.entities.permission_grant import GrantablePermission
from grouper.entities.permission_request import PermissionRequest
from grouper.models.group import Group as SQLGroup
from grouper.models.permission import Permission as SQLPermission
from grouper.models.permission_request import PermissionRequest as SQLPermissionRequest
from grouper.repositories.interfaces import PermissionRequestRepository

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import List


class SQLPermissionRequestRepository(PermissionRequestRepository):
    """SQL storage layer for permission requests."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def pending_requests_for_group(self, groupname):
        # type: (str) -> List[PermissionRequest]
        sql_results = (
            self.session.query(
                label("group", SQLGroup.name),
                label("permission", SQLPermission.name),
                label("argument", SQLPermissionRequest.argument),
                label("status", SQLPermissionRequest.status),
            )
            .filter(
                SQLGroup.groupname == groupname,
                SQLGroup.id == SQLPermissionRequest.group_id,
                SQLPermissionRequest.permission_id == SQLPermission.id,
                SQLPermissionRequest.status == "pending",
            )
            .all()
        )
        return [
            PermissionRequest(
                group=r.group,
                grant=GrantablePermission(name=r.permission, argument=r.argument),
                status=r.status,
            )
            for r in sql_results
        ]
