from typing import TYPE_CHECKING

import pytest

from grouper.constants import PERMISSION_ADMIN
from grouper.permissions import get_permission
from tests.ctl_util import run_ctl

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_permission_disable(setup):
    # type: (SetupTest) -> None
    setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
    setup.add_user_to_group("gary@a.co", "admins")
    setup.create_permission("some-permission")
    setup.commit()

    run_ctl(setup, "permission", "-a", "gary@a.co", "disable", "some-permission")
    permission = get_permission(setup.session, "some-permission")
    assert permission
    assert not permission.enabled


def test_permission_disable_failed(setup):
    # type: (SetupTest) -> None
    setup.create_user("gary@a.co")
    setup.commit()
    with pytest.raises(SystemExit):
        run_ctl(setup, "permission", "-a", "gary@a.co", "disable", "some-permission")
