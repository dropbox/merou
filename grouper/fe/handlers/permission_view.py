from typing import TYPE_CHECKING

from grouper.fe.util import GrouperHandler
from grouper.usecases.view_permission import ViewPermissionUI

if TYPE_CHECKING:
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.entities.permission import Permission, PermissionAccess
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
    )
    from typing import Any, List


class PermissionView(GrouperHandler, ViewPermissionUI):
    def viewed_permission(
        self,
        permission,  # type: Permission
        group_grants,  # type: List[GroupPermissionGrant]
        service_account_grants,  # type: List[ServiceAccountPermissionGrant]
        access,  # type: PermissionAccess
        audit_log_entries,  # type: List[AuditLogEntry]
    ):
        # type (...) -> None
        self.render(
            "permission.html",
            permission=permission,
            access=access,
            group_grants=group_grants,
            service_account_grants=service_account_grants,
            audit_log_entries=audit_log_entries,
        )

    def view_permission_failed_not_found(self, name):
        # type: (str) -> None
        self.notfound()

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        name = kwargs["name"]  # type: str
        usecase = self.usecase_factory.create_view_permission_usecase(self)
        usecase.view_permission(name, self.current_user.username, audit_log_limit=20)
