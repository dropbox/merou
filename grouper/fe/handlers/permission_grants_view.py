from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.entities.pagination import PaginatedList, Pagination, PermissionGrantSortKey
from grouper.fe.templates import PermissionGrantsTemplate
from grouper.fe.util import GrouperHandler
from grouper.usecases.view_permission_grants import GrantType, ViewPermissionGrantsUI

if TYPE_CHECKING:
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.entities.permission import Permission, PermissionAccess
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
    )
    from typing import Any, List, Union


class PermissionGrantsView(GrouperHandler, ViewPermissionGrantsUI):
    def view_permission_failed_not_found(self, name: str) -> None:
        self.notfound()

    def viewed_permission(
        self,
        permission: Permission,
        grants: Union[
            PaginatedList[GroupPermissionGrant], PaginatedList[ServiceAccountPermissionGrant]
        ],
        access: PermissionAccess,
        audit_log_entries: List[AuditLogEntry],
    ) -> None:

        template_html = (
            "permission-group.html"
            if "/groups" in self.request.uri
            else "permission-service-account.html"
        )

        print("Sending data {}".format(grants))

        sort_key = self.get_argument("sort_by", "name")
        sort_dir = self.get_argument("order", "asc")

        template = PermissionGrantsTemplate(
            permission=permission,
            access=access,
            grants=grants.values,
            audit_log_entries=audit_log_entries,
            template=template_html,
            offset=grants.offset,
            limit=grants.limit or 100,
            total=grants.total,
            sort_key=sort_key,
            sort_dir=sort_dir,
        )
        self.render_template_class(template)

    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")
        argument = self.get_argument("argument", None)

        grant_type = GrantType.Group if "/groups" in self.request.uri else GrantType.ServiceAccount

        offset = int(self.get_argument("offset", "0"))
        limit = int(self.get_argument("limit", "100"))

        sort_key_str = self.get_argument("sort_by", None)
        if sort_key_str:
            sort_key = PermissionGrantSortKey(sort_key_str)
        else:
            sort_key = (
                PermissionGrantSortKey.GROUP
                if grant_type == GrantType.Group
                else PermissionGrantSortKey.SERVICE_ACCOUNT
            )

        sort_dir = self.get_argument("order", "asc")
        pagination = Pagination(
            sort_key=sort_key, reverse_sort=(sort_dir == "desc"), offset=offset, limit=limit
        )

        usecase = self.usecase_factory.create_view_permission_grants_usecase(self)
        usecase.view_granted_permission(
            name,
            self.current_user.username,
            audit_log_limit=20,
            grant_type=grant_type,
            argument=argument,
            pagination=pagination,
        )
