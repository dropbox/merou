from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.entities.pagination import (
    PaginatedList,
    Pagination,
    PermissionServiceAccountGrantSortKey,
)
from grouper.fe.templates import PermissionServiceAccountGrantsTemplate
from grouper.fe.util import GrouperHandler
from grouper.usecases.view_permission_service_account_grants import (
    ViewPermissionServiceAccountGrantsUI,
)

if TYPE_CHECKING:
    from grouper.entities.permission import Permission
    from grouper.entities.permission_grant import ServiceAccountPermissionGrant
    from typing import Any


class PermissionGrantsServiceAccountView(GrouperHandler, ViewPermissionServiceAccountGrantsUI):
    def view_permission_failed_not_found(self, name: str) -> None:
        self.notfound()

    def get_sort_key(self) -> PermissionServiceAccountGrantSortKey:
        sort_key_str = self.get_argument("sort_by", None)
        if sort_key_str:
            return PermissionServiceAccountGrantSortKey(sort_key_str)
        else:
            return PermissionServiceAccountGrantSortKey.SERVICE_ACCOUNT

    def viewed_permission(
        self, permission: Permission, grants: PaginatedList[ServiceAccountPermissionGrant]
    ) -> None:

        sort_key = self.get_sort_key().name.lower()
        sort_dir = self.get_argument("order", "asc")

        template = PermissionServiceAccountGrantsTemplate(
            permission=permission,
            grants=grants.values,
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

        offset = int(self.get_argument("offset", "0"))
        limit = int(self.get_argument("limit", "100"))
        sort_key = self.get_sort_key()
        sort_dir = self.get_argument("order", "asc")
        pagination = Pagination(
            sort_key=sort_key, reverse_sort=(sort_dir == "desc"), offset=offset, limit=limit
        )

        usecase = self.usecase_factory.create_view_permission_service_account_grants_usecase(self)
        usecase.view_granted_permission(
            name, self.current_user.username, argument=argument, pagination=pagination
        )
