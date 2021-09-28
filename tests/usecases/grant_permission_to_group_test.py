from typing import TYPE_CHECKING

from mock import ANY, call, MagicMock

from grouper.constants import ARGUMENT_VALIDATION, PERMISSION_ADMIN, PERMISSION_GRANT
from grouper.entities.permission_grant import GroupPermissionGrant

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_permissions_grantable(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.grant_permission_to_group("some-permission", "arg_one", "some-group")
        setup.grant_permission_to_group("some-permission", "arg_two", "some-group")
        setup.grant_permission_to_group("other-permission", "*", "some-group")

        # Admins should be able to grant all permissions
        setup.add_user_to_group("zorkian@a.co", "admin-group")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admin-group")
        setup.create_service_account("admin@svc.localhost", "admin-group")
        setup.grant_permission_to_service_account(PERMISSION_ADMIN, "", "admin@svc.localhost")

        setup.add_user_to_group("rra@a.co", "granter-group")
        setup.grant_permission_to_group(PERMISSION_GRANT, "some-permission", "granter-group")
        setup.create_service_account("granter@svc.localhost", "granter-group")
        setup.grant_permission_to_service_account(
            PERMISSION_GRANT, "some-permission/arg", "granter@svc.localhost"
        )
        # User with no special permissions should not be able to grant anything.
        setup.create_user("permless@a.co")

    mock_ui = MagicMock()

    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase("rra@a.co", mock_ui)
    expected = [("some-permission", "*")]
    assert usecase.permissions_grantable() == expected

    all_permissions = ["some-permission", "other-permission", PERMISSION_ADMIN, PERMISSION_GRANT]
    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase(
        "zorkian@a.co", mock_ui
    )
    expected = sorted([(perm, "*") for perm in all_permissions])
    assert usecase.permissions_grantable() == expected

    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase(
        "admin@svc.localhost", mock_ui
    )
    assert usecase.permissions_grantable() == expected

    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase(
        "granter@svc.localhost", mock_ui
    )
    expected = [("some-permission", "arg")]
    assert usecase.permissions_grantable() == expected

    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase("gary@a.co", mock_ui)
    assert usecase.permissions_grantable() == []

    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase(
        "service@svc.localhost", mock_ui
    )
    assert usecase.permissions_grantable() == []

    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase(
        "permless@a.co", mock_ui
    )
    assert usecase.permissions_grantable() == []


def _test_success(setup, actor):
    # type: (SetupTest, str) -> None

    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.grant_permission_to_group("some-permission", "argument", "some-group")
        setup.create_permission("other-permission")
        setup.add_user_to_group("zorkian@a.co", "admins")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.create_service_account("admin@svc.localhost", "admins")
        setup.grant_permission_to_service_account(PERMISSION_ADMIN, "", "admin@svc.localhost")
        setup.create_service_account("granter@svc.localhost", "other-group")
        setup.grant_permission_to_group(PERMISSION_GRANT, "some-permission/arg*", "some-group")

    service = setup.service_factory.create_group_service()
    assert len(service.permission_grants_for_group("some-group")) == 2

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase(actor, mock_ui)
    usecase.grant_permission_to_group("some-permission", "different_argument", "some-group")
    assert mock_ui.mock_calls == [
        call.granted_permission_to_group("some-permission", "different_argument", "some-group")
    ]
    expected = GroupPermissionGrant(
        group="some-group",
        permission="some-permission",
        argument="different_argument",
        granted_on=ANY,
        is_alias=False,
        grant_id=ANY,
    )
    setup.graph.update_from_db(setup.session)
    grants = service.permission_grants_for_group("some-group")
    assert len(grants) == 3
    assert expected in grants


def test_success_user(setup):
    # type: (SetupTest) -> None
    _test_success(setup, "zorkian@a.co")


def test_success_service_account(setup):
    # type: (SetupTest) -> None
    _test_success(setup, "admin@svc.localhost")


def test_duplicate_grant(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.grant_permission_to_group("some-permission", "argument", "some-group")
        setup.grant_permission_to_group(PERMISSION_GRANT, "some-permission/arg*", "some-group")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase("gary@a.co", mock_ui)
    usecase.grant_permission_to_group("some-permission", "argument", "some-group")
    assert mock_ui.mock_calls == [
        call.grant_permission_to_group_failed_permission_already_exists("some-group")
    ]


def test_invalid_argument(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.create_permission("some-permission")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase("gary@a.co", mock_ui)
    usecase.grant_permission_to_group("some-permission", "@@@@", "some-group")
    assert mock_ui.mock_calls == [
        call.grant_permission_to_group_failed_invalid_argument(
            "some-permission",
            "@@@@",
            "some-group",
            "Permission argument is not valid (does not match {})".format(ARGUMENT_VALIDATION),
        )
    ]


def _assert_sane_permission_denied_message(mock_ui):
    # type: (MagicMock) -> None
    # Check the mock's first call ([0]) non-keyword args ([1]) last arg ([-1]),
    # which in permission denied cases is the error message.
    assert mock_ui.mock_calls[0][1][-1].startswith("Permission denied")


def test_permission_denied(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_user("gary@a.co")
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.create_permission("some-permission")
        setup.grant_permission_to_group("other-permission", "*", "some-group")

    # User with no special permissions.
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase("gary@a.co", mock_ui)
    usecase.grant_permission_to_group("some-permission", "argument", "some-group")
    assert mock_ui.mock_calls == [
        call.grant_permission_to_group_failed_permission_denied(
            "some-permission", "argument", "some-group", ANY
        )
    ]
    _assert_sane_permission_denied_message(mock_ui)

    # Service account with no special permissions.
    mock_ui.reset_mock()
    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase(
        "service@svc.localhost", mock_ui
    )
    usecase.grant_permission_to_group("some-permission", "argument", "some-group")
    assert mock_ui.mock_calls == [
        call.grant_permission_to_group_failed_permission_denied(
            "some-permission", "argument", "some-group", ANY
        )
    ]
    _assert_sane_permission_denied_message(mock_ui)

    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    mock_ui.reset_mock()
    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase("gary@a.co", mock_ui)
    usecase.grant_permission_to_group("some-permission", "argument", "some-group")
    assert mock_ui.mock_calls == [
        call.grant_permission_to_group_failed_permission_denied(
            "some-permission", "argument", "some-group", ANY
        )
    ]
    _assert_sane_permission_denied_message(mock_ui)


def test_unknown_group(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.create_permission("some-permission")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_grant_permission_to_group_usecase("gary@a.co", mock_ui)
    usecase.grant_permission_to_group("some-permission", "argument", "another-group")
    assert mock_ui.mock_calls == [
        call.grant_permission_to_group_failed_group_not_found("another-group")
    ]
