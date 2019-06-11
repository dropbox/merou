from typing import TYPE_CHECKING

import pytest

from grouper.constants import PERMISSION_ADMIN
from grouper.permissions import get_permission
from tests.ctl_util import run_ctl

if TYPE_CHECKING:
    from pytest.logging import LogCaptureFixture
    from tests.setup import SetupTest


def test_disable(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.create_permission("some-permission")

    run_ctl(setup, "permission", "-a", "gary@a.co", "disable", "some-permission")
    permission = get_permission(setup.session, "some-permission")
    assert permission
    assert not permission.enabled


def test_disable_failed(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_user("gary@a.co")
    with pytest.raises(SystemExit):
        run_ctl(setup, "permission", "-a", "gary@a.co", "disable", "some-permission")


def test_disable_with_existing_grants(setup, caplog):
    # type: (SetupTest, LogCaptureFixture) -> None
    with setup.transaction():
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group("some-permission", "", "some-group")

    with pytest.raises(SystemExit):
        run_ctl(setup, "permission", "-a", "gary@a.co", "disable", "some-permission")

    assert "permission some-permission still granted to groups some-group" in caplog.text


def test_disable_with_duplicate_grants(setup, caplog):
    # type: (SetupTest, LogCaptureFixture) -> None
    with setup.transaction():
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group("some-permission", "", "some-group")
        setup.grant_permission_to_group("some-permission", "foo", "another-group")
        setup.grant_permission_to_group("some-permission", "bar", "another-group")
        setup.grant_permission_to_group("some-permission", "baz", "another-group")

    with pytest.raises(SystemExit):
        run_ctl(setup, "permission", "-a", "gary@a.co", "disable", "some-permission")

    expected = "permission some-permission still granted to groups another-group, some-group"
    assert expected in caplog.text
