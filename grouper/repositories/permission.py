from typing import TYPE_CHECKING

from grouper.entities.pagination import ListPermissionsSortKey, PaginatedList
from grouper.entities.permission import Permission, PermissionNotFoundException
from grouper.models.permission import Permission as SQLPermission
from grouper.repositories.interfaces import PermissionRepository

if TYPE_CHECKING:
    from datetime import datetime
    from grouper.entities.pagination import Pagination
    from grouper.graph import GroupGraph
    from grouper.models.base.session import Session
    from typing import Optional


class GraphPermissionRepository(PermissionRepository):
    """Graph-aware storage layer for permissions."""

    # Mapping from ListPermissionsSortKey to the name of an attribute on the Permission returned by
    # get_permissions() on the graph.
    SORT_FIELD = {ListPermissionsSortKey.NAME: "name", ListPermissionsSortKey.DATE: "created_on"}

    def __init__(self, graph, repository):
        # type: (GroupGraph, PermissionRepository) -> None
        self.graph = graph
        self.repository = repository

    def create_permission(
        self, name, description="", audited=False, enabled=True, created_on=None
    ):
        # type: (str, str, bool, bool, Optional[datetime]) -> None
        self.repository.create_permission(name, description, audited, enabled, created_on)

    def disable_permission(self, name):
        # type: (str) -> None
        self.repository.disable_permission(name)

    def get_permission(self, name):
        # type: (str) -> Optional[Permission]
        return self.repository.get_permission(name)

    def list_permissions(self, pagination, audited_only):
        # type: (Pagination[ListPermissionsSortKey], bool) -> PaginatedList[Permission]
        permissions = self.graph.get_permissions(audited=audited_only)

        # Optionally sort.
        if pagination.sort_key != ListPermissionsSortKey.NONE:
            permissions = sorted(
                permissions,
                key=lambda p: getattr(p, self.SORT_FIELD[pagination.sort_key]),
                reverse=pagination.reverse_sort,
            )

        # Find the total length and then optionally slice.
        total = len(permissions)
        if pagination.limit:
            permissions = permissions[pagination.offset : pagination.offset + pagination.limit]
        elif pagination.offset > 0:
            permissions = permissions[pagination.offset :]

        # Convert to the correct data transfer object and return.
        return PaginatedList[Permission](
            values=permissions, total=total, offset=pagination.offset, limit=pagination.limit
        )


class SQLPermissionRepository(PermissionRepository):
    """SQL storage layer for permissions."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def create_permission(
        self, name, description="", audited=False, enabled=True, created_on=None
    ):
        # type: (str, str, bool, bool, Optional[datetime]) -> None
        permission = SQLPermission(
            name=name, description=description, audited=audited, enabled=enabled
        )
        if created_on:
            permission.created_on = created_on
        permission.add(self.session)

    def disable_permission(self, name):
        # type: (str) -> None
        permission = SQLPermission.get(self.session, name=name)
        if not permission:
            raise PermissionNotFoundException(name)
        permission.enabled = False

    def get_permission(self, name):
        # type: (str) -> Optional[Permission]
        permission = SQLPermission.get(self.session, name=name)
        if not permission:
            return None
        return Permission(
            name=permission.name,
            description=permission.description,
            created_on=permission.created_on,
            audited=permission.audited,
            enabled=permission.enabled,
        )

    def list_permissions(self, pagination, audited_only):
        # type: (Pagination[ListPermissionsSortKey], bool) -> PaginatedList[Permission]
        raise NotImplementedError()
