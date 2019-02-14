from datetime import datetime
from typing import TYPE_CHECKING

from grouper.constants import PERMISSION_CREATE
from grouper.entities.pagination import PaginatedList, Pagination
from grouper.entities.permission import Permission
from grouper.graph import GroupGraph
from grouper.models.base.constants import OBJ_TYPES
from grouper.models.counter import Counter
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.permission import Permission as SQLPermission
from grouper.models.permission_map import PermissionMap
from grouper.models.user import User
from grouper.repositories.factory import RepositoryFactory
from grouper.services.factory import ServiceFactory
from grouper.usecases.factory import UseCaseFactory
from grouper.usecases.list_permissions import ListPermissionsSortKey, ListPermissionsUI
from tests.fixtures import session  # noqa: F401

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.usecases.list_permissions import ListPermissions
    from typing import Any, List, Optional


class MockUI(ListPermissionsUI):
    def __init__(self, sort=False):
        # type: (bool) -> None
        self.sort = sort

    def listed_permissions(self, permissions, can_create):
        # type: (PaginatedList[Permission], bool) -> None
        self.permissions = permissions
        if self.sort:
            self.permissions.values = sorted(self.permissions.values)
        self.can_create = can_create


def assert_paginated_list_equal(left, right):
    # type: (PaginatedList[Any], PaginatedList[Any]) -> None
    """mypy NamedTuples don't compare with simple equality."""
    assert left.values == right.values
    assert left.total == right.total
    assert left.offset == right.offset


def create_test_data(session):  # noqa: F811
    # type: (Session) -> List[Permission]
    """Sets up a very basic test graph and returns the permission objects."""
    early_date = datetime.utcfromtimestamp(1)
    permissions = [
        Permission(name="first-permission", description="first", created_on=datetime.utcnow()),
        Permission(name="audited-permission", description="", created_on=datetime.utcnow()),
        Permission(name="early-permission", description="is early", created_on=early_date),
    ]
    for permission in permissions:
        sql_permission = SQLPermission(
            name=permission.name,
            description=permission.description,
            created_on=permission.created_on,
        )
        sql_permission.add(session)
    SQLPermission.get(session, name="audited-permission")._audited = True
    SQLPermission(name="disabled", description="", enabled=False).add(session)
    User(username="gary@a.co").add(session)
    Counter.incr(session, "updates")
    session.commit()
    return permissions


def create_list_permissions_usecase(session, ui, graph=None):  # noqa: F811
    # type: (Session, ListPermissionsUI, Optional[GroupGraph]) -> ListPermissions
    if not graph:
        graph = GroupGraph()
    graph.update_from_db(session)
    repository_factory = RepositoryFactory(session, graph)
    service_factory = ServiceFactory(session, repository_factory)
    usecase_factory = UseCaseFactory(service_factory)
    return usecase_factory.create_list_permissions_usecase(ui)


def test_simple_list_permissions(session):  # noqa: F811
    # type: (Session) -> None
    permissions = create_test_data(session)
    mock_ui = MockUI(sort=True)
    usecase = create_list_permissions_usecase(session, mock_ui)
    usecase.simple_list_permissions()
    assert not mock_ui.can_create
    expected = PaginatedList(values=sorted(permissions), total=3, offset=0)
    assert_paginated_list_equal(mock_ui.permissions, expected)


def test_list_permissions_pagination(session):  # noqa: F811
    # type: (Session) -> None
    permissions = create_test_data(session)
    mock_ui = MockUI()
    usecase = create_list_permissions_usecase(session, mock_ui)

    # Sorted by name, limited to 2.
    pagination = Pagination(
        sort_key=ListPermissionsSortKey.NAME, reverse_sort=False, offset=0, limit=2
    )
    usecase.list_permissions("gary@a.co", pagination, audited_only=False)
    expected = PaginatedList(values=sorted(permissions)[:2], total=3, offset=0)
    assert_paginated_list_equal(mock_ui.permissions, expected)

    # Sorted by date, using offset, limit longer than remaining items.
    pagination = Pagination(
        sort_key=ListPermissionsSortKey.DATE, reverse_sort=False, offset=2, limit=10
    )
    usecase.list_permissions("gary@a.co", pagination, audited_only=False)
    expected_values = sorted(permissions, key=lambda p: p.created_on)[2:]
    expected = PaginatedList(values=expected_values, total=3, offset=2)
    assert_paginated_list_equal(mock_ui.permissions, expected)

    # Sorted by name, reversed, limit of one 1 and offset of 1.
    pagination = Pagination(
        sort_key=ListPermissionsSortKey.NAME, reverse_sort=True, offset=1, limit=1
    )
    usecase.list_permissions("gary@a.co", pagination, audited_only=False)
    expected_values = sorted(permissions, reverse=True)[1:2]
    expected = PaginatedList(values=expected_values, total=3, offset=1)
    assert_paginated_list_equal(mock_ui.permissions, expected)


def test_list_permissions_audited_only(session):  # noqa: F811
    # type: (Session) -> None
    permissions = create_test_data(session)
    mock_ui = MockUI()
    usecase = create_list_permissions_usecase(session, mock_ui)
    pagination = Pagination(
        sort_key=ListPermissionsSortKey.NAME, reverse_sort=False, offset=0, limit=None
    )
    usecase.list_permissions("gary@a.co", pagination, audited_only=True)
    expected_values = [p for p in permissions if p.name == "audited-permission"]
    expected = PaginatedList(values=expected_values, total=1, offset=0)
    assert_paginated_list_equal(mock_ui.permissions, expected)


def test_list_permissions_can_create(session):  # noqa: F811
    # type: (Session) -> None
    user = User(username="gary@a.co")
    user.add(session)
    SQLPermission(name=PERMISSION_CREATE, description="").add(session)
    Counter.incr(session, "updates")
    session.commit()
    graph = GroupGraph()
    mock_ui = MockUI()
    usecase = create_list_permissions_usecase(session, mock_ui, graph)

    # User has no permissions.
    pagination = Pagination(
        sort_key=ListPermissionsSortKey.NAME, reverse_sort=False, offset=0, limit=None
    )
    usecase.list_permissions("gary@a.co", pagination, audited_only=False)
    assert not mock_ui.can_create

    # Create a group, grant the permission to the group, and add the user to the group.
    permission = SQLPermission.get(session, name=PERMISSION_CREATE)
    group = Group(groupname="creators")
    group.add(session)
    GroupEdge(
        group_id=group.id, member_type=OBJ_TYPES["User"], member_pk=user.id, active=True
    ).add(session)
    PermissionMap(permission_id=permission.id, group_id=group.id, argument="*").add(session)
    Counter.incr(session, "updates")
    session.commit()
    graph.update_from_db(session)

    # Now the can_create flag should be set to true.
    usecase.list_permissions("gary@a.co", pagination, audited_only=False)
    assert mock_ui.can_create
