from typing import TYPE_CHECKING

import pytest
from mock import ANY

from grouper.constants import DEFAULT_ADMIN_GROUP, ILLEGAL_NAME_CHARACTER
from grouper.entities.group import GroupJoinPolicy, InvalidGroupNameException
from grouper.entities.permission_grant import GroupPermissionGrant

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_permission_grants_for_group(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group("some-permission", "one", "some-group")
        setup.grant_permission_to_group("some-permission", "two", "some-group")
        setup.grant_permission_to_group("other-permission", "*", "some-group")
        setup.grant_permission_to_group("parent-permission", "foo", "parent-group")
        setup.add_group_to_group("some-group", "parent-group")
        setup.create_group("other-group")
        setup.create_user("gary@a.co")

    service = setup.service_factory.create_group_service()
    expected = [
        GroupPermissionGrant(
            group="some-group",
            permission="other-permission",
            argument="*",
            granted_on=ANY,
            is_alias=False,
            grant_id=ANY,
        ),
        GroupPermissionGrant(
            group="some-group",
            permission="parent-permission",
            argument="foo",
            granted_on=ANY,
            is_alias=False,
            grant_id=ANY,
        ),
        GroupPermissionGrant(
            group="some-group",
            permission="some-permission",
            argument="one",
            granted_on=ANY,
            is_alias=False,
            grant_id=ANY,
        ),
        GroupPermissionGrant(
            group="some-group",
            permission="some-permission",
            argument="two",
            granted_on=ANY,
            is_alias=False,
            grant_id=ANY,
        ),
    ]
    assert sorted(service.permission_grants_for_group("some-group")) == expected
    assert service.permission_grants_for_group("other-group") == []


def test_invalid_group_name(setup):
    # type: (SetupTest) -> None
    group_service = setup.service_factory.create_group_service()
    assert group_service.is_valid_group_name(DEFAULT_ADMIN_GROUP)
    assert not group_service.is_valid_group_name("group name")
    assert not group_service.is_valid_group_name("group{}name".format(ILLEGAL_NAME_CHARACTER))
    with pytest.raises(InvalidGroupNameException):
        group_service.create_group("group name", "", GroupJoinPolicy.NOBODY)
