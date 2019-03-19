from typing import TYPE_CHECKING

import pytest
from mock import call, MagicMock

from grouper.constants import USER_ADMIN
from grouper.entities.group import GroupNotFoundException
from grouper.graph import NoSuchUser
from grouper.group_requests import count_requests_by_group
from grouper.models.group import Group
from grouper.models.group_service_accounts import GroupServiceAccount
from grouper.models.service_account import ServiceAccount
from grouper.models.user import User

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_success(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group(USER_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.create_user("service@a.co")
        setup.create_group("some-group")
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_convert_user_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    usecase.convert_user_to_service_account("service@a.co", "some-group")
    assert mock_ui.mock_calls == [
        call.converted_user_to_service_account("service@a.co", "some-group")
    ]

    # Check the User after the conversion
    service_account_user = User.get(setup.session, name="service@a.co")
    assert service_account_user
    assert service_account_user.is_service_account
    assert service_account_user.enabled

    # Check the ServiceAccount that should have been created
    service_account = ServiceAccount.get(setup.session, name="service@a.co")
    assert service_account
    assert service_account.description == ""
    assert service_account.machine_set == ""
    assert service_account.user_id == service_account_user.id

    # Check that the ServiceAccount is owned by the correct Group
    group = Group.get(setup.session, name="some-group")
    group_service_account = GroupServiceAccount.get(
        setup.session, service_account_id=service_account.id
    )
    assert group
    assert group_service_account
    assert group_service_account.group_id == group.id


def test_failed_access_denied(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "admins")
        setup.create_user("service@a.co")
        setup.create_group("some-group")
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_convert_user_to_service_account_usecase(
        "gary@a.co", mock_ui
    )

    usecase.convert_user_to_service_account("service@a.co", "some-group")
    assert mock_ui.mock_calls == [
        call.convert_user_to_service_account_failed_permission_denied("service@a.co")
    ]


def test_failed_member_of_group(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group(USER_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.create_user("service@a.co")
        setup.add_user_to_group("service@a.co", "admins")
        setup.create_group("some-group")
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_convert_user_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    usecase.convert_user_to_service_account("service@a.co", "some-group")
    assert mock_ui.mock_calls == [
        call.convert_user_to_service_account_failed_user_is_in_groups("service@a.co")
    ]


def test_cancels_group_requests(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group(USER_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.create_user("service@a.co")
        setup.create_group("some-group")
        setup.create_group_request("service@a.co", "some-group")
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_convert_user_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    usecase.convert_user_to_service_account("service@a.co", "some-group")
    assert mock_ui.mock_calls == [
        call.converted_user_to_service_account("service@a.co", "some-group")
    ]

    # Confirm that the request to the group is now cancelled and there are no pending requests
    group = Group.get(setup.session, name="some-group")
    assert group
    assert count_requests_by_group(setup.session, group, status="cancelled") == 1
    assert count_requests_by_group(setup.session, group, status="pending") == 0


def test_failed_user_does_not_exist(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group(USER_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.create_group("some-group")
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_convert_user_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    with pytest.raises(NoSuchUser):
        usecase.convert_user_to_service_account("dne@a.co", "some-group")


def test_failed_group_does_not_exist(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group(USER_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.create_user("service@a.co")
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_convert_user_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    with pytest.raises(GroupNotFoundException):
        usecase.convert_user_to_service_account("service@a.co", "some-group")
