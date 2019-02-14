from grouper.entities.pagination import PaginatedList, Pagination
from grouper.entities.permission import Permission
from grouper.fe.util import GrouperHandler
from grouper.repositories.factory import RepositoryFactory
from grouper.services.factory import ServiceFactory
from grouper.usecases.factory import UseCaseFactory
from grouper.usecases.list_permissions import ListPermissionsSortKey, ListPermissionsUI


class PermissionsView(GrouperHandler, ListPermissionsUI):
    """Controller for viewing the major permissions list.

    There is no privacy here; the existence of a permission is public.
    """

    def listed_permissions(self, permissions, can_create):
        # type: (PaginatedList[Permission], bool) -> None
        audited_only = bool(int(self.get_argument("audited", 0)))
        sort_key = self.get_argument("sort_by", "name")
        sort_dir = self.get_argument("order", "asc")
        self.render(
            "permissions.html",
            permissions=permissions.values,
            offset=permissions.offset,
            limit=len(permissions.values),
            total=permissions.total,
            can_create=can_create,
            audited_permissions=audited_only,
            sort_key=sort_key,
            sort_dir=sort_dir,
        )

    def get(self, audited_only=False):
        self.handle_refresh()
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        audited_only = bool(int(self.get_argument("audited", 0)))
        sort_key = ListPermissionsSortKey(self.get_argument("sort_by", "name"))
        sort_dir = self.get_argument("order", "asc")

        pagination = Pagination(
            sort_key=sort_key, reverse_sort=(sort_dir == "desc"), offset=offset, limit=limit
        )

        repository_factory = RepositoryFactory(self.session, self.graph)
        service_factory = ServiceFactory(self.session, repository_factory)
        usecase_factory = UseCaseFactory(service_factory)
        usecase = usecase_factory.create_list_permissions_usecase(self)
        usecase.list_permissions(self.current_user.name, pagination, audited_only)
