from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from grouper.constants import AUDIT_MANAGER, PERMISSION_ADMIN
from grouper.entities.audit_log_entry import AuditLogEntry
from grouper.entities.pagination import (
    Pagination,
    PermissionGroupGrantSortKey,
    PermissionServiceAccountGrantSortKey,
)
from grouper.usecases.authorization import Authorization
from grouper.usecases.view_permission import ViewPermissionUI
from grouper.usecases.view_permission_group_grants import (
    GroupListType,
    ViewPermissionGroupGrantsUI,
)
from grouper.usecases.view_permission_service_account_grants import (
    ServiceAccountListType,
    ViewPermissionServiceAccountGrantsUI,
)

if TYPE_CHECKING:
    from typing import List
    from grouper.entities.permission import Permission, PermissionAccess
    from tests.setup import SetupTest


class MockGroupUI(ViewPermissionGroupGrantsUI):
    def view_permission_failed_not_found(self, name):
        # type: (str) -> None
        self.failed = True

    def viewed_permission(
        self,
        permission,  # type: Permission
        grants,  # type: GroupListType
    ):
        # type (...) -> None
        self.permission = permission
        self.grants = grants


class MockServiceAccountUI(ViewPermissionServiceAccountGrantsUI):
    def view_permission_failed_not_found(self, name):
        # type: (str) -> None
        self.failed = True

    def viewed_permission(
        self,
        permission,  # type: Permission
        grants,  # type: ServiceAccountListType
    ):
        # type (...) -> None
        self.permission = permission
        self.grants = grants


class MockPermissionUI(ViewPermissionUI):
    def view_permission_failed_not_found(self, name):
        # type: (str) -> None
        self.failed = True

    def viewed_permission(
        self,
        permission,  # type: Permission
        access,  # type: PermissionAccess
        audit_log_entries,  # type: List[AuditLogEntry]
    ):
        # type (...) -> None
        self.permission = permission
        self.access = access
        self.audit_log_entries = audit_log_entries


def test_view_permissions(setup):
    # type: (SetupTest) -> None
    mock_group_ui = MockGroupUI()
    mock_service_account_ui = MockServiceAccountUI()
    mock_permission_ui = MockPermissionUI()

    usecase_factory = setup.usecase_factory

    group_usecase = usecase_factory.create_view_permission_group_grants_usecase(mock_group_ui)
    sa_usecase = usecase_factory.create_view_permission_service_account_grants_usecase(
        mock_service_account_ui
    )
    permission_usecase = usecase_factory.create_view_permission_usecase(mock_permission_ui)

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
    group_paginate = Pagination(
        sort_key=PermissionGroupGrantSortKey.GROUP, reverse_sort=False, offset=0, limit=100
    )
    service_account_paginate = Pagination(
        sort_key=PermissionServiceAccountGrantSortKey.SERVICE_ACCOUNT,
        reverse_sort=False,
        offset=0,
        limit=100,
    )

    group_usecase.view_granted_permission("some-permission", "gary@a.co", group_paginate)
    sa_usecase.view_granted_permission("some-permission", "gary@a.co", service_account_paginate)
    permission_usecase.view_permission("some-permission", "gary@a.co", 20)

    assert mock_group_ui.permission.name == "some-permission"
    assert mock_service_account_ui.permission.name == "some-permission"
    assert mock_group_ui.permission.description == "Some permission"
    assert mock_service_account_ui.permission.description == "Some permission"
    assert not mock_permission_ui.permission.audited
    assert mock_permission_ui.permission.enabled
    assert not mock_permission_ui.access.can_disable
    assert not mock_permission_ui.access.can_change_audited_status

    group_grants = [(g.group, g.permission, g.argument) for g in mock_group_ui.grants.values]
    assert group_grants == [
        ("another-group", "some-permission", ""),
        ("some-group", "some-permission", "foo"),
    ]
    assert mock_service_account_ui.grants.values == []
    assert mock_permission_ui.audit_log_entries == []

    # Audited permission without group grants but some service account grants.
    group_usecase.view_granted_permission("audited-permission", "gary@a.co", group_paginate)
    sa_usecase.view_granted_permission("audited-permission", "gary@a.co", service_account_paginate)

    assert mock_group_ui.permission.name == "audited-permission"
    assert mock_service_account_ui.permission.name == "audited-permission"
    assert mock_group_ui.permission.description == ""
    assert mock_service_account_ui.permission.description == ""

    assert mock_group_ui.grants.values == []
    service_account_grants = [
        (g.service_account, g.permission, g.argument)
        for g in mock_service_account_ui.grants.values
    ]
    assert service_account_grants == [("service@svc.localhost", "audited-permission", "argument")]

    # Disabled permission with some log entries.
    group_usecase.view_granted_permission("disabled-permission", "gary@a.co", group_paginate)
    sa_usecase.view_granted_permission(
        "disabled-permission", "gary@a.co", service_account_paginate
    )
    permission_usecase.view_permission("disabled-permission", "gary@a.co", 20)

    assert mock_group_ui.permission.name == "disabled-permission"
    assert mock_service_account_ui.permission.name == "disabled-permission"
    assert not mock_permission_ui.permission.audited
    assert not mock_permission_ui.permission.enabled
    assert mock_group_ui.grants.values == []
    assert mock_service_account_ui.grants.values == []
    audit_log_entries = [
        (e.actor, e.action, e.on_permission) for e in mock_permission_ui.audit_log_entries
    ]
    assert audit_log_entries == [
        ("gary@a.co", "disable_permission", "disabled-permission"),
        ("gary@a.co", "create_permission", "disabled-permission"),
    ]

    # Limit the number of audit log entries.
    permission_usecase.view_permission("disabled-permission", "gary@a.co", 1)
    audit_log_entries = [
        (e.actor, e.action, e.on_permission) for e in mock_permission_ui.audit_log_entries
    ]
    assert audit_log_entries == [("gary@a.co", "disable_permission", "disabled-permission")]

    # Search for permission based on argument with group grants and service account grants.
    group_usecase.view_granted_permission(
        "argumented-permission", "gary@a.co", group_paginate, "foo-arg"
    )
    sa_usecase.view_granted_permission(
        "argumented-permission", "gary@a.co", service_account_paginate, "foo-arg"
    )
    permission_usecase.view_permission("argumented-permission", "gary@a.co", 20)

    assert mock_group_ui.permission.name == "argumented-permission"
    assert mock_service_account_ui.permission.name == "argumented-permission"
    assert mock_group_ui.permission.description == "Some argumented permission"
    assert mock_service_account_ui.permission.description == "Some argumented permission"
    assert not mock_permission_ui.permission.audited
    assert mock_permission_ui.permission.enabled
    group_grants = [(g.group, g.permission, g.argument) for g in mock_group_ui.grants.values]
    assert group_grants == [("some-group", "argumented-permission", "foo-arg")]
    service_account_grants = [
        (g.service_account, g.permission, g.argument)
        for g in mock_service_account_ui.grants.values
    ]
    assert service_account_grants == [
        ("service_for_argumented_permission@svc.localhost", "argumented-permission", "foo-arg")
    ]

    # Search for permission based on argument which isn't present
    group_usecase.view_granted_permission(
        "argumented-permission", "gary@a.co", group_paginate, "foo"
    )
    sa_usecase.view_granted_permission(
        "argumented-permission", "gary@a.co", service_account_paginate, "foo"
    )
    permission_usecase.view_permission("argumented-permission", "gary@a.co", 20)

    assert mock_group_ui.permission.name == "argumented-permission"
    assert mock_service_account_ui.permission.name == "argumented-permission"
    assert mock_group_ui.permission.description == "Some argumented permission"
    assert mock_service_account_ui.permission.description == "Some argumented permission"
    assert not mock_permission_ui.permission.audited
    assert mock_permission_ui.permission.enabled
    group_grants = [(g.group, g.permission, g.argument) for g in mock_group_ui.grants.values]
    assert group_grants == []
    service_account_grants = [
        (g.service_account, g.permission, g.argument)
        for g in mock_service_account_ui.grants.values
    ]
    assert service_account_grants == []


def test_view_permissions_access(setup):
    # type: (SetupTest) -> None

    mock_permission_ui = MockPermissionUI()
    permission_usecase = setup.usecase_factory.create_view_permission_usecase(mock_permission_ui)

    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "audit-managers")
        setup.grant_permission_to_group(AUDIT_MANAGER, "", "audit-managers")
        setup.create_permission("some-permission", "Some permission")

    # Can manage audited permissions, but is not a permission admin.
    permission_usecase.view_permission("some-permission", "gary@a.co", 20)
    assert mock_permission_ui.access.can_change_audited_status
    assert not mock_permission_ui.access.can_disable

    with setup.transaction():
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "audit-managers")
        setup.add_user_to_group("zorkian@a.co", "grouper-administrators")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "grouper-administrators")

    # Now is both a permission admin and an audit manager.
    permission_usecase.view_permission("some-permission", "gary@a.co", 20)
    assert mock_permission_ui.access.can_change_audited_status
    assert mock_permission_ui.access.can_disable

    # Just having permission admin is enough.
    permission_usecase.view_permission("some-permission", "zorkian@a.co", 20)
    assert mock_permission_ui.access.can_change_audited_status
    assert mock_permission_ui.access.can_disable


def test_pagination(setup):
    # type: (SetupTest) -> None

    with setup.transaction():
        setup.create_permission("permission1", "")

        setup.grant_permission_to_group("permission", "arg0", "group0")
        setup.grant_permission_to_group("permission", "arg1", "group1")
        setup.grant_permission_to_group("permission", "arg2", "group2")

        setup.create_user("gary@a.co")

    mock_group_ui = MockGroupUI()
    group_usecase = setup.usecase_factory.create_view_permission_group_grants_usecase(
        mock_group_ui
    )

    for offset in [0, 1, 2]:
        group_paginate = Pagination(
            sort_key=PermissionGroupGrantSortKey.GROUP, reverse_sort=False, offset=offset, limit=1
        )
        group_usecase.view_granted_permission("permission", "gary@a.co", group_paginate)
        group_grants = [(g.group, g.permission, g.argument) for g in mock_group_ui.grants.values]
        assert group_grants == [("group{}".format(offset), "permission", "arg{}".format(offset))]
