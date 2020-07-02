from dataclasses import replace
from datetime import datetime
from time import time
from typing import TYPE_CHECKING

from grouper.constants import PERMISSION_CREATE
from grouper.entities.pagination import ListPermissionsSortKey, PaginatedList, Pagination
from grouper.entities.permission import Permission
from grouper.usecases.list_permissions import ListPermissionsUI

if TYPE_CHECKING:
    from tests.setup import SetupTest
    from typing import List


class MockUI(ListPermissionsUI):
    def __init__(self, sort: bool = False) -> None:
        self.sort = sort

    def listed_permissions(self, permissions: PaginatedList[Permission], can_create: bool) -> None:
        if self.sort:
            self.permissions = replace(permissions, values=sorted(permissions.values))
        else:
            self.permissions = permissions
        self.can_create = can_create


def create_test_data(setup):
    # type: (SetupTest) -> List[Permission]
    """Sets up a very basic test graph and returns the permission objects.

    Be careful not to include milliseconds in the creation timestamps since this causes different
    behavior on SQLite (which preserves them) and MySQL (which drops them).
    """
    early_date = datetime.utcfromtimestamp(1)
    now_minus_one_second = datetime.utcfromtimestamp(int(time() - 1))
    now = datetime.utcfromtimestamp(int(time()))
    permissions = [
        Permission(
            name="first-permission",
            description="first",
            created_on=now_minus_one_second,
            audited=False,
            enabled=True,
        ),
        Permission(
            name="audited-permission", description="", created_on=now, audited=True, enabled=True
        ),
        Permission(
            name="early-permission",
            description="is early",
            created_on=early_date,
            audited=False,
            enabled=True,
        ),
    ]
    with setup.transaction():
        for permission in permissions:
            setup.create_permission(
                name=permission.name,
                description=permission.description,
                created_on=permission.created_on,
                audited=permission.audited,
            )
        setup.create_permission("disabled", enabled=False)
        setup.create_user("gary@a.co")
    return permissions


def test_simple_list_permissions(setup):
    # type: (SetupTest) -> None
    permissions = create_test_data(setup)
    mock_ui = MockUI(sort=True)
    usecase = setup.usecase_factory.create_list_permissions_usecase(mock_ui)
    usecase.simple_list_permissions()
    assert not mock_ui.can_create
    expected = PaginatedList(values=sorted(permissions), total=3, offset=0, limit=None)
    assert mock_ui.permissions == expected


def test_list_permissions_pagination(setup):
    # type: (SetupTest) -> None
    permissions = create_test_data(setup)
    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_list_permissions_usecase(mock_ui)

    # Sorted by name, limited to 2.
    pagination = Pagination(
        sort_key=ListPermissionsSortKey.NAME, reverse_sort=False, offset=0, limit=2
    )
    usecase.list_permissions("gary@a.co", pagination, audited_only=False)
    expected = PaginatedList(values=sorted(permissions)[:2], total=3, offset=0, limit=2)
    assert mock_ui.permissions == expected

    # Sorted by date, using offset, limit longer than remaining items.
    pagination = Pagination(
        sort_key=ListPermissionsSortKey.DATE, reverse_sort=False, offset=2, limit=10
    )
    usecase.list_permissions("gary@a.co", pagination, audited_only=False)
    expected_values = sorted(permissions, key=lambda p: p.created_on)[2:]
    expected = PaginatedList(values=expected_values, total=3, offset=2, limit=10)
    assert mock_ui.permissions == expected

    # Sorted by name, reversed, limit of one 1 and offset of 1.
    pagination = Pagination(
        sort_key=ListPermissionsSortKey.NAME, reverse_sort=True, offset=1, limit=1
    )
    usecase.list_permissions("gary@a.co", pagination, audited_only=False)
    expected_values = sorted(permissions, reverse=True)[1:2]
    expected = PaginatedList(values=expected_values, total=3, offset=1, limit=1)
    assert mock_ui.permissions == expected


def test_list_permissions_audited_only(setup):
    # type: (SetupTest) -> None
    permissions = create_test_data(setup)
    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_list_permissions_usecase(mock_ui)
    pagination = Pagination(
        sort_key=ListPermissionsSortKey.NAME, reverse_sort=False, offset=0, limit=None
    )
    usecase.list_permissions("gary@a.co", pagination, audited_only=True)
    expected_values = [p for p in permissions if p.name == "audited-permission"]
    expected = PaginatedList(values=expected_values, total=1, offset=0, limit=None)
    assert mock_ui.permissions == expected


def test_list_permissions_can_create(setup):
    # type: (SetupTest) -> None
    setup.create_permission(PERMISSION_CREATE)
    create_test_data(setup)
    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_list_permissions_usecase(mock_ui)

    # User has no permissions.
    pagination = Pagination(
        sort_key=ListPermissionsSortKey.NAME, reverse_sort=False, offset=0, limit=None
    )
    usecase.list_permissions("gary@a.co", pagination, audited_only=False)
    assert not mock_ui.can_create

    # If the user is added to a group with the right permission, can_create should be true.
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "creators")
        setup.grant_permission_to_group(PERMISSION_CREATE, "*", "creators")
    usecase.list_permissions("gary@a.co", pagination, audited_only=False)
    assert mock_ui.can_create
