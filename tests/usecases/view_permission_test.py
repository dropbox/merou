from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from grouper.constants import AUDIT_MANAGER, PERMISSION_ADMIN
from grouper.usecases.authorization import Authorization
from grouper.usecases.view_permission import ViewPermissionUI

if TYPE_CHECKING:
    from grouper.entities.audit_log_entry import AuditLogEntry
    from grouper.entities.permission import Permission, PermissionAccess
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
    )
    from tests.setup import SetupTest
    from typing import List


class MockUI(ViewPermissionUI):
    def view_permission_failed_not_found(self, name):
        # type: (str) -> None
        self.failed = True

    def viewed_permission(
        self,
        permission,  # type: Permission
        group_grants,  # type: List[GroupPermissionGrant]
        service_account_grants,  # type: List[ServiceAccountPermissionGrant]
        access,  # type: PermissionAccess
        audit_log_entries,  # type: List[AuditLogEntry]
    ):
        # type (...) -> None
        self.permission = permission
        self.group_grants = group_grants
        self.service_account_grants = service_account_grants
        self.access = access
        self.audit_log_entries = audit_log_entries


def test_view_permissions(setup):
    # type: (SetupTest) -> None
    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_view_permission_usecase(mock_ui)
    with setup.transaction():
        setup.create_permission("audited-permission", "", audited=True)
        setup.create_permission("some-permission", "Some permission")
        setup.create_permission("disabled-permission", "", enabled=False)
        setup.create_permission("argumented-permission", "Some argumented permission")
        setup.grant_permission_to_group("some-permission", "", "another-group")
        setup.grant_permission_to_group("some-permission", "foo", "some-group")
        setup.grant_permission_to_group("argumented-permission", "foo-arg", "some-group")
        setup.create_service_account("service@svc.localhost", "owner-group")
        setup.create_service_account(
            "service_for_argumented_permission@svc.localhost", "foo-group"
        )
        setup.grant_permission_to_service_account(
            "audited-permission", "argument", "service@svc.localhost"
        )
        setup.grant_permission_to_service_account(
            "argumented-permission", "foo-arg", "service_for_argumented_permission@svc.localhost"
        )
        setup.create_user("gary@a.co")
        audit_log_service = setup.service_factory.create_audit_log_service()
        authorization = Authorization("gary@a.co")
        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        audit_log_service.log_create_permission(
            "disabled-permission", authorization, date=one_minute_ago
        )
        audit_log_service.log_disable_permission("disabled-permission", authorization)

    # Regular permission with some group grants.
    usecase.view_permission("some-permission", "gary@a.co", 20)
    assert mock_ui.permission.name == "some-permission"
    assert mock_ui.permission.description == "Some permission"
    assert not mock_ui.permission.audited
    assert mock_ui.permission.enabled
    group_grants = [(g.group, g.permission, g.argument) for g in mock_ui.group_grants]
    assert group_grants == [
        ("another-group", "some-permission", ""),
        ("some-group", "some-permission", "foo"),
    ]
    assert mock_ui.service_account_grants == []
    assert not mock_ui.access.can_disable
    assert not mock_ui.access.can_change_audited_status
    assert mock_ui.audit_log_entries == []

    # Audited permission without group grants but some service account grants.
    usecase.view_permission("audited-permission", "gary@a.co", 20)
    assert mock_ui.permission.name == "audited-permission"
    assert mock_ui.permission.description == ""
    assert mock_ui.permission.audited
    assert mock_ui.permission.enabled
    assert mock_ui.group_grants == []
    service_account_grants = [
        (g.service_account, g.permission, g.argument) for g in mock_ui.service_account_grants
    ]
    assert service_account_grants == [("service@svc.localhost", "audited-permission", "argument")]

    # Disabled permission with some log entries.
    usecase.view_permission("disabled-permission", "gary@a.co", 20)
    assert mock_ui.permission.name == "disabled-permission"
    assert not mock_ui.permission.audited
    assert not mock_ui.permission.enabled
    assert mock_ui.group_grants == []
    assert mock_ui.service_account_grants == []
    audit_log_entries = [(e.actor, e.action, e.on_permission) for e in mock_ui.audit_log_entries]
    assert audit_log_entries == [
        ("gary@a.co", "disable_permission", "disabled-permission"),
        ("gary@a.co", "create_permission", "disabled-permission"),
    ]

    # Limit the number of audit log entries.
    usecase.view_permission("disabled-permission", "gary@a.co", 1)
    audit_log_entries = [(e.actor, e.action, e.on_permission) for e in mock_ui.audit_log_entries]
    assert audit_log_entries == [("gary@a.co", "disable_permission", "disabled-permission")]

    # Search for permission based on argument with group grants and service account grants.
    usecase.view_permission("argumented-permission", "gary@a.co", 20, "foo-arg")
    assert mock_ui.permission.name == "argumented-permission"
    assert mock_ui.permission.description == "Some argumented permission"
    assert not mock_ui.permission.audited
    assert mock_ui.permission.enabled
    group_grants = [(g.group, g.permission, g.argument) for g in mock_ui.group_grants]
    assert group_grants == [
        ("some-group", "argumented-permission", "foo-arg"),
    ]
    service_account_grants = [
        (g.service_account, g.permission, g.argument) for g in mock_ui.service_account_grants
    ]
    assert service_account_grants == [
        ("service_for_argumented_permission@svc.localhost", "argumented-permission", "foo-arg")
    ]

    # Search for permission based on argument which isn't present
    usecase.view_permission("argumented-permission", "gary@a.co", 20, "foo")
    assert mock_ui.permission.name == "argumented-permission"
    assert mock_ui.permission.description == "Some argumented permission"
    assert not mock_ui.permission.audited
    assert mock_ui.permission.enabled
    assert mock_ui.group_grants == []
    service_account_grants = [
        (g.service_account, g.permission, g.argument) for g in mock_ui.service_account_grants
    ]
    assert service_account_grants == []


def test_view_permissions_access(setup):
    # type: (SetupTest) -> None
    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_view_permission_usecase(mock_ui)
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "audit-managers")
        setup.grant_permission_to_group(AUDIT_MANAGER, "", "audit-managers")
        setup.create_permission("some-permission", "Some permission")

    # Can manage audited permissions, but is not a permission admin.
    usecase.view_permission("some-permission", "gary@a.co", 20)
    assert mock_ui.access.can_change_audited_status
    assert not mock_ui.access.can_disable

    with setup.transaction():
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "audit-managers")
        setup.add_user_to_group("zorkian@a.co", "grouper-administrators")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "grouper-administrators")

    # Now is both a permission admin and an audit manager.
    usecase.view_permission("some-permission", "gary@a.co", 20)
    assert mock_ui.access.can_change_audited_status
    assert mock_ui.access.can_disable

    # Just having permission admin is enough.
    usecase.view_permission("some-permission", "zorkian@a.co", 20)
    assert mock_ui.access.can_change_audited_status
    assert mock_ui.access.can_disable
