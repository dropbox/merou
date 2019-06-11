from typing import TYPE_CHECKING

from grouper.constants import (
    GROUP_ADMIN,
    PERMISSION_ADMIN,
    PERMISSION_AUDITOR,
    SYSTEM_PERMISSIONS,
    USER_ADMIN,
)
from grouper.models.group import Group

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_initialize_schema(setup):
    # type: (SetupTest) -> None
    setup.settings.auditors_group = "auditors"
    usecase = setup.usecase_factory.create_initialize_schema_usecase()
    usecase.initialize_schema()

    # System permissions should be created.
    permission_service = setup.service_factory.create_permission_service()
    for permission, _ in SYSTEM_PERMISSIONS:
        assert permission_service.permission_exists(permission)

    # The admin group should exist and have a selection of administrative permissions.
    admin_group = Group.get(setup.session, name="grouper-administrators")
    assert admin_group
    admin_group_permissions = [p.name for p in admin_group.my_permissions()]
    for permission in (GROUP_ADMIN, PERMISSION_ADMIN, USER_ADMIN):
        assert permission in admin_group_permissions

    # The auditors group should exist and have the auditor permission.
    auditors_group = Group.get(setup.session, name="auditors")
    assert auditors_group
    auditors_group_permissions = [p.name for p in auditors_group.my_permissions()]
    assert PERMISSION_AUDITOR in auditors_group_permissions


def test_initialize_schema_twice(setup):
    # type: (SetupTest) -> None
    setup.settings.auditors_group = "auditors"
    usecase = setup.usecase_factory.create_initialize_schema_usecase()
    usecase.initialize_schema()
    usecase.initialize_schema()
