from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.templates import PermissionTemplate
from grouper.fe.util import GrouperHandler
from grouper.usecases.view_permission import ViewPermissionUI

if TYPE_CHECKING:
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.entities.permission import Permission, PermissionAccess
    from typing import Any, List


class PermissionView(GrouperHandler, ViewPermissionUI):
    def view_permission_failed_not_found(self, name: str) -> None:
        self.notfound()

    def viewed_permission(
        self,
        permission: Permission,
        access: PermissionAccess,
        audit_log_entries: List[AuditLogEntry],
    ) -> None:
        template = PermissionTemplate(
            permission=permission, access=access, audit_log_entries=audit_log_entries
        )
        self.render_template_class(template)

    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")
        argument = self.get_argument("argument", None)

        usecase = self.usecase_factory.create_view_permission_usecase(self)
        usecase.view_permission(
            name, self.current_user.username, audit_log_limit=20, argument=argument
        )
