from typing import TYPE_CHECKING

from mock import ANY, call, MagicMock

from grouper.constants import ARGUMENT_VALIDATION, PERMISSION_ADMIN
from grouper.entities.permission_grant import GroupPermissionGrant, ServiceAccountPermissionGrant

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

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
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
    assert sorted(usecase.permission_grants_for_group("some-group")) == expected
    assert usecase.permission_grants_for_group("other-group") == []


def test_service_account_exists_with_owner(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.create_service_account("other@svc.localhost", "some-group")
        setup.create_group("other-group")
        setup.disable_service_account("other@svc.localhost")
        setup.create_user("gary@a.co")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    assert usecase.service_account_exists_with_owner("service@svc.localhost", "some-group")
    assert not usecase.service_account_exists_with_owner("service@svc.localhost", "bogus-group")
    assert not usecase.service_account_exists_with_owner("service@svc.localhost", "other-group")
    assert not usecase.service_account_exists_with_owner("other@svc.localhost", "some-group")
    assert not usecase.service_account_exists_with_owner("bogus@svc.localhost", "some-group")


def test_success(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.grant_permission_to_group("some-permission", "argument", "some-group")
        setup.create_permission("other-permission")
        setup.add_user_to_group("zorkian@a.co", "admins")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.create_service_account("admin@svc.localhost", "admins")
        setup.grant_permission_to_service_account(PERMISSION_ADMIN, "", "admin@svc.localhost")

    service = setup.service_factory.create_service_account_service()
    assert service.permission_grants_for_service_account("service@svc.localhost") == []

    # Delegation from a group member.
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    assert usecase.can_grant_permissions_for_service_account("service@svc.localhost")
    usecase.grant_permission_to_service_account(
        "some-permission", "argument", "service@svc.localhost"
    )
    assert mock_ui.mock_calls == [
        call.granted_permission_to_service_account(
            "some-permission", "argument", "service@svc.localhost"
        )
    ]
    expected = [
        ServiceAccountPermissionGrant(
            service_account="service@svc.localhost",
            permission="some-permission",
            argument="argument",
            granted_on=ANY,
            is_alias=False,
            grant_id=ANY,
        )
    ]
    setup.graph.update_from_db(setup.session)
    assert service.permission_grants_for_service_account("service@svc.localhost") == expected

    # Delegation from permission admin.
    mock_ui.reset_mock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "zorkian@a.co", mock_ui
    )
    assert usecase.can_grant_permissions_for_service_account("service@svc.localhost")
    usecase.grant_permission_to_service_account(
        "other-permission", "argument", "service@svc.localhost"
    )
    assert mock_ui.mock_calls == [
        call.granted_permission_to_service_account(
            "other-permission", "argument", "service@svc.localhost"
        )
    ]
    expected.append(
        ServiceAccountPermissionGrant(
            service_account="service@svc.localhost",
            permission="other-permission",
            argument="argument",
            granted_on=ANY,
            is_alias=False,
            grant_id=ANY,
        )
    )
    setup.graph.update_from_db(setup.session)
    assert service.permission_grants_for_service_account("service@svc.localhost") == expected

    # Delegation from a permission admin that happens to be a service account.
    mock_ui.reset_mock()
    assert usecase.can_grant_permissions_for_service_account("service@svc.localhost")
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "admin@svc.localhost", mock_ui
    )
    usecase.grant_permission_to_service_account("other-permission", "*", "service@svc.localhost")
    assert mock_ui.mock_calls == [
        call.granted_permission_to_service_account(
            "other-permission", "*", "service@svc.localhost"
        )
    ]
    expected.append(
        ServiceAccountPermissionGrant(
            service_account="service@svc.localhost",
            permission="other-permission",
            argument="*",
            granted_on=ANY,
            is_alias=False,
            grant_id=ANY,
        )
    )
    setup.graph.update_from_db(setup.session)
    assert service.permission_grants_for_service_account("service@svc.localhost") == expected


def test_wildcard(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.grant_permission_to_group("some-permission", "*", "some-group")
        setup.create_service_account("service@svc.localhost", "some-group")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    usecase.grant_permission_to_service_account(
        "some-permission", "argument", "service@svc.localhost"
    )
    assert mock_ui.mock_calls == [
        call.granted_permission_to_service_account(
            "some-permission", "argument", "service@svc.localhost"
        )
    ]
    expected = [
        ServiceAccountPermissionGrant(
            service_account="service@svc.localhost",
            permission="some-permission",
            argument="argument",
            granted_on=ANY,
            is_alias=False,
            grant_id=ANY,
        )
    ]
    setup.graph.update_from_db(setup.session)
    service = setup.service_factory.create_service_account_service()
    assert service.permission_grants_for_service_account("service@svc.localhost") == expected


def test_invalid_argument(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.create_permission("some-permission")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    usecase.grant_permission_to_service_account("some-permission", "@@@@", "service@svc.localhost")
    assert mock_ui.mock_calls == [
        call.grant_permission_to_service_account_failed_invalid_argument(
            "some-permission",
            "@@@@",
            "service@svc.localhost",
            "Permission argument is not valid (does not match {})".format(ARGUMENT_VALIDATION),
        )
    ]


def test_permission_denied(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_user("gary@a.co")
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.create_permission("some-permission")

    # User with no special permissions.
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    assert not usecase.can_grant_permissions_for_service_account("service@svc.localhost")
    usecase.grant_permission_to_service_account(
        "some-permission", "argument", "service@svc.localhost"
    )
    assert mock_ui.mock_calls == [
        call.grant_permission_to_service_account_failed_permission_denied(
            "some-permission", "argument", "service@svc.localhost", "Permission denied"
        )
    ]

    # Service account with no special permissions.
    mock_ui.reset_mock()
    assert not usecase.can_grant_permissions_for_service_account("service@svc.localhost")
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "service@svc.localhost", mock_ui
    )
    usecase.grant_permission_to_service_account(
        "some-permission", "argument", "service@svc.localhost"
    )
    assert mock_ui.mock_calls == [
        call.grant_permission_to_service_account_failed_permission_denied(
            "some-permission", "argument", "service@svc.localhost", "Permission denied"
        )
    ]

    # Add the user to the group, but don't delegate the permission to the group.  The user should
    # now be able to grant permissions in general, but not this permission in particular.
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    mock_ui.reset_mock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    assert usecase.can_grant_permissions_for_service_account("service@svc.localhost")
    usecase.grant_permission_to_service_account(
        "some-permission", "argument", "service@svc.localhost"
    )
    assert mock_ui.mock_calls == [
        call.grant_permission_to_service_account_failed_permission_denied(
            "some-permission",
            "argument",
            "service@svc.localhost",
            "The group some-group does not have that permission",
        )
    ]


def test_unknown_permission(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.create_service_account("service@svc.localhost", "some-group")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    usecase.grant_permission_to_service_account(
        "some-permission", "argument", "service@svc.localhost"
    )
    assert mock_ui.mock_calls == [
        call.grant_permission_to_service_account_failed_permission_not_found(
            "some-permission", "service@svc.localhost"
        )
    ]


def test_unknown_service_account(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.create_permission("some-permission")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    usecase.grant_permission_to_service_account(
        "some-permission", "argument", "service@svc.localhost"
    )
    assert mock_ui.mock_calls == [
        call.grant_permission_to_service_account_failed_service_account_not_found(
            "service@svc.localhost"
        )
    ]
