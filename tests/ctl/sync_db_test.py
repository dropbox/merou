from typing import TYPE_CHECKING

from grouper.constants import (
    GROUP_ADMIN,
    PERMISSION_ADMIN,
    PERMISSION_AUDITOR,
    SYSTEM_PERMISSIONS,
    USER_ADMIN,
)
from grouper.models.group import Group
from grouper.settings import Settings
from tests.ctl_util import run_ctl
from tests.path_util import src_path

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_sync_db(setup):
    # type: (SetupTest) -> None
    run_ctl(setup, "sync_db")

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

    # We reuse config/dev.yaml when testing, but someone may have changed the auditors_group
    # setting there.  Figure out the current setting.
    dev_settings = Settings()
    dev_settings.update_from_config(src_path("config", "dev.yaml"))

    # The auditors group should exist and have the auditor permission.
    if dev_settings.auditors_group:
        auditors_group = Group.get(setup.session, name=dev_settings.auditors_group)
        assert auditors_group
        auditors_group_permissions = [p.name for p in auditors_group.my_permissions()]
        assert PERMISSION_AUDITOR in auditors_group_permissions
