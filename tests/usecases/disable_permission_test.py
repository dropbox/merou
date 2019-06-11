from typing import TYPE_CHECKING

from mock import ANY, call, MagicMock

from grouper.constants import PERMISSION_ADMIN, PERMISSION_CREATE
from grouper.entities.permission_grant import GroupPermissionGrant, ServiceAccountPermissionGrant
from grouper.models.permission import Permission

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_permission_disable(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.create_permission("some-permission")
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_disable_permission_usecase("gary@a.co", mock_ui)

    usecase.disable_permission("some-permission")
    assert mock_ui.mock_calls == [call.disabled_permission("some-permission")]
    assert not Permission.get(setup.session, name="some-permission").enabled

    audit_log_service = setup.service_factory.create_audit_log_service()
    audit_log_entries = audit_log_service.entries_affecting_permission("some-permission", 20)
    assert len(audit_log_entries) == 1
    assert audit_log_entries[0].actor == "gary@a.co"
    assert audit_log_entries[0].action == "disable_permission"
    assert audit_log_entries[0].on_permission == "some-permission"


def test_permission_disable_inactive_grants(setup):
    # type: (SetupTest) -> None
    """Test that permission grants to disabled objects are automatically deleted."""
    with setup.transaction():
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group("some-permission", "argument", "some-group")
        setup.disable_group("some-group")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_disable_permission_usecase("gary@a.co", mock_ui)
    usecase.disable_permission("some-permission")
    assert mock_ui.mock_calls == [call.disabled_permission("some-permission")]
    permission_grant_repository = setup.repository_factory.create_permission_grant_repository()
    grants = permission_grant_repository.group_grants_for_permission(
        "some-permission", include_disabled_groups=True
    )
    assert grants == []


def test_permission_disable_denied(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_user("zorkian@a.co")
        setup.create_permission("some-permission")
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_disable_permission_usecase("zorkian@a.co", mock_ui)
    usecase.disable_permission("some-permission")
    assert mock_ui.mock_calls == [
        call.disable_permission_failed_permission_denied("some-permission")
    ]
    assert Permission.get(setup.session, name="some-permission").enabled


def test_permission_disable_existing_grants(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group("some-permission", "argument", "some-group")
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.grant_permission_to_service_account("some-permission", "", "service@svc.localhost")

    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_disable_permission_usecase("gary@a.co", mock_ui)
    usecase.disable_permission("some-permission")
    assert mock_ui.mock_calls == [
        call.disable_permission_failed_existing_grants(
            "some-permission",
            [
                GroupPermissionGrant(
                    group="some-group",
                    permission="some-permission",
                    argument="argument",
                    granted_on=ANY,
                    is_alias=False,
                    grant_id=ANY,
                )
            ],
            [
                ServiceAccountPermissionGrant(
                    service_account="service@svc.localhost",
                    permission="some-permission",
                    argument="",
                    granted_on=ANY,
                    is_alias=False,
                    grant_id=ANY,
                )
            ],
        )
    ]


def test_permission_disable_system(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.create_permission(PERMISSION_CREATE)
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_disable_permission_usecase("gary@a.co", mock_ui)
    usecase.disable_permission(PERMISSION_CREATE)
    assert mock_ui.mock_calls == [
        call.disable_permission_failed_system_permission(PERMISSION_CREATE)
    ]


def test_permission_not_found(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
    mock_ui = MagicMock()
    usecase = setup.usecase_factory.create_disable_permission_usecase("gary@a.co", mock_ui)
    usecase.disable_permission("nonexistent")
    assert mock_ui.mock_calls == [call.disable_permission_failed_not_found("nonexistent")]
