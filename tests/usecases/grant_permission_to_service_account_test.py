from typing import TYPE_CHECKING

from mock import ANY, call, MagicMock

from grouper.constants import ARGUMENT_VALIDATION, PERMISSION_ADMIN, PERMISSION_GRANT
from grouper.entities.permission_grant import ServiceAccountPermissionGrant

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_permissions_grantable_to_service_account(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        # Serivce account in an owning group that has some perms, should all be grantable
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.grant_permission_to_group("some-permission", "arg_one", "some-group")
        setup.grant_permission_to_group("some-permission", "arg_two", "some-group")
        setup.grant_permission_to_group("other-permission", "*", "some-group")
        # Admin user and service account, should be able to grant _all_ permissions
        setup.add_user_to_group("zorkian@a.co", "admin-group")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admin-group")
        setup.create_service_account("admin@svc.localhost", "admin-group")
        setup.grant_permission_to_service_account(PERMISSION_ADMIN, "", "admin@svc.localhost")
        # User and service account with PERMISSION_GRANT; should be able to grant relevant perms
        setup.add_user_to_group("rra@a.co", "granter-group")
        setup.grant_permission_to_group(PERMISSION_GRANT, "some-permission", "granter-group")
        setup.create_service_account("granter@svc.localhost", "granter-group")
        setup.grant_permission_to_service_account(
            PERMISSION_GRANT, "some-permission/arg", "granter@svc.localhost"
        )
        # User with no special permissions should not be able to grant anything.
        setup.create_user("permless@a.co")

    mock_ui = MagicMock()

    # For members of the owning group, owner group perms are included
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    expected = [  # alphabetically sorted
        ("other-permission", "*"),
        ("some-permission", "arg_one"),
        ("some-permission", "arg_two"),
    ]
    assert usecase.permissions_grantable_to_service_account("service@svc.localhost") == expected

    # For admins, _all_ permissions are included with "*" as the argument
    all_permissions = ["some-permission", "other-permission", PERMISSION_ADMIN, PERMISSION_GRANT]
    expected = sorted([(perm, "*") for perm in all_permissions])

    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "zorkian@a.co", mock_ui
    )
    assert usecase.permissions_grantable_to_service_account("service@svc.localhost") == expected

    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "admin@svc.localhost", mock_ui
    )
    assert usecase.permissions_grantable_to_service_account("service@svc.localhost") == expected

    # For all other users, only include permissions the user can independently grant
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "rra@a.co", mock_ui
    )
    expected = [("some-permission", "*")]
    assert usecase.permissions_grantable_to_service_account("service@svc.localhost") == expected

    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "granter@svc.localhost", mock_ui
    )
    expected = [("some-permission", "arg")]
    assert usecase.permissions_grantable_to_service_account("service@svc.localhost") == expected

    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "permless@a.co", mock_ui
    )
    assert usecase.permissions_grantable_to_service_account("service@svc.localhost") == []


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
        setup.create_service_account("granter@svc.localhost", "other-group")
        setup.grant_permission_to_service_account(
            PERMISSION_GRANT, "some-permission/arg*", "granter@svc.localhost"
        )

    service = setup.service_factory.create_service_account_service()
    assert service.permission_grants_for_service_account("service@svc.localhost") == []

    # Delegation from a group member.
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
    assert service.permission_grants_for_service_account("service@svc.localhost") == expected

    # Delegation from permission admin.
    mock_ui.reset_mock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "zorkian@a.co", mock_ui
    )
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

    # Delegation from an independent granter that happens to be a service account.
    mock_ui.reset_mock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "granter@svc.localhost", mock_ui
    )
    usecase.grant_permission_to_service_account("some-permission", "argA", "service@svc.localhost")
    assert mock_ui.mock_calls == [
        call.granted_permission_to_service_account(
            "some-permission", "argA", "service@svc.localhost"
        )
    ]
    expected.append(
        ServiceAccountPermissionGrant(
            service_account="service@svc.localhost",
            permission="some-permission",
            argument="argA",
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
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    usecase.grant_permission_to_service_account(
        "some-permission", "argument", "service@svc.localhost"
    )
    assert mock_ui.mock_calls == [
        call.grant_permission_to_service_account_failed_permission_denied(
            "some-permission", "argument", "service@svc.localhost", ANY
        )
    ]
    _assert_sane_permission_denied_message(mock_ui)

    # Service account with no special permissions.
    mock_ui.reset_mock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "service@svc.localhost", mock_ui
    )
    usecase.grant_permission_to_service_account(
        "some-permission", "argument", "service@svc.localhost"
    )
    assert mock_ui.mock_calls == [
        call.grant_permission_to_service_account_failed_permission_denied(
            "some-permission", "argument", "service@svc.localhost", ANY
        )
    ]
    _assert_sane_permission_denied_message(mock_ui)

    # Add the user to the group, but don't delegate the permission to the group.  The user should
    # now be able to grant permissions in general, but not this permission in particular.
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    mock_ui.reset_mock()
    usecase = setup.usecase_factory.create_grant_permission_to_service_account_usecase(
        "gary@a.co", mock_ui
    )
    usecase.grant_permission_to_service_account(
        "some-permission", "argument", "service@svc.localhost"
    )
    assert mock_ui.mock_calls == [
        call.grant_permission_to_service_account_failed_permission_denied(
            "some-permission", "argument", "service@svc.localhost", ANY
        )
    ]
    _assert_sane_permission_denied_message(mock_ui)


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
