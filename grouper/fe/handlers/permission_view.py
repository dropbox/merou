from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.templates import PermissionTemplate
from grouper.fe.util import GrouperHandler
from grouper.usecases.view_permission import ViewPermissionUI
from grouper.entities.pagination import ListPermissionsSortKey, PaginatedList, Pagination

if TYPE_CHECKING:
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.entities.permission import Permission, PermissionAccess
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
    )
    from typing import Any, List


class PermissionView(GrouperHandler, ViewPermissionUI):
    def view_permission_failed_not_found(self, name: str) -> None:
        self.notfound()

    def viewed_permission(
        self,
        permission: Permission,
        group_grants: PaginatedList[GroupPermissionGrant],
        service_account_grants: PaginatedList[ServiceAccountPermissionGrant],
        access: PermissionAccess,
        audit_log_entries: List[AuditLogEntry],
    ) -> None:
        template = PermissionTemplate(
            permission=permission,
            access=access,
            group_grants=group_grants,
            service_account_grants=service_account_grants,
            audit_log_entries=audit_log_entries,
            offset=service_account_grants.offset,
            limit=service_account_grants.limit or 100,
            total=service_account_grants.total+group_grants.total,
        )
        self.render_template_class(template)

    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        offset = int(self.get_argument("offset", "0"))
        limit = int(self.get_argument("limit", "100"))
        sort_key = ListPermissionsSortKey(self.get_argument("sort_by", "name"))
        sort_dir = self.get_argument("order", "asc")
        pagination = Pagination(
            sort_key=sort_key, reverse_sort=(sort_dir == "desc"), offset=offset, limit=limit
        )

        argument = self.get_argument("argument", None)
        usecase = self.usecase_factory.create_view_permission_usecase(self)
        usecase.view_permission(
            name, self.current_user.username, audit_log_limit=20, argument=argument
        )
