from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.entities.pagination import ListPermissionsSortKey, PaginatedList, Pagination
from grouper.entities.permission import Permission
from grouper.fe.templates import PermissionsTemplate
from grouper.fe.util import GrouperHandler
from grouper.usecases.list_permissions import ListPermissionsUI

if TYPE_CHECKING:
    from typing import Any


class PermissionsView(GrouperHandler, ListPermissionsUI):
    def listed_permissions(self, permissions: PaginatedList[Permission], can_create: bool) -> None:
        audited_only = bool(int(self.get_argument("audited", "0")))
        sort_key = self.get_argument("sort_by", "name")
        sort_dir = self.get_argument("order", "asc")

        template = PermissionsTemplate(
            permissions=permissions.values,
            offset=permissions.offset,
            limit=permissions.limit or 100,
            total=permissions.total,
            can_create=can_create,
            audited_permissions=audited_only,
            sort_key=sort_key,
            sort_dir=sort_dir,
        )
        self.render_template_class(template)

    def get(self, *args: Any, **kwargs: Any) -> None:
        self.handle_refresh()
        offset = int(self.get_argument("offset", "0"))
        limit = int(self.get_argument("limit", "100"))
        audited_only = bool(int(self.get_argument("audited", "0")))
        sort_key = ListPermissionsSortKey(self.get_argument("sort_by", "name"))
        sort_dir = self.get_argument("order", "asc")

        pagination = Pagination(
            sort_key=sort_key, reverse_sort=(sort_dir == "desc"), offset=offset, limit=limit
        )

        usecase = self.usecase_factory.create_list_permissions_usecase(self)
        usecase.list_permissions(self.current_user.name, pagination, audited_only)
