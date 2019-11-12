from __future__ import annotations

from typing import TYPE_CHECKING

from groupy.client import Groupy

from grouper.constants import GROUP_ADMIN, USER_ADMIN
from itests.setup import api_server

if TYPE_CHECKING:
    from py.local import LocalPath
    from tests.setup import SetupTest


def test_get_users(tmpdir: LocalPath, setup: SetupTest) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.create_user("zorkian@a.co")
        setup.create_user("disabled@a.co")
        setup.disable_user("disabled@a.co")
        setup.create_service_account("service@a.co", "some-group")
        setup.create_role_user("role@a.co")

    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        assert sorted(api_client.users) == ["disabled@a.co", "gary@a.co", "zorkian@a.co"]


def test_get_user(tmpdir: LocalPath, setup: SetupTest) -> None:
    with setup.transaction():
        setup.add_user_to_group("cbguder@a.co", "admins")
        setup.grant_permission_to_group(GROUP_ADMIN, "", "admins")
        setup.grant_permission_to_group(USER_ADMIN, "", "admins")
        setup.add_user_to_group("cbguder@a.co", "some-group")
        setup.grant_permission_to_group("some-permission", "one", "some-group")
        setup.add_group_to_group("some-group", "parent-group")
        setup.grant_permission_to_group("some-permission", "two", "some-group")

    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        user = api_client.users.get("cbguder@a.co")

        assert sorted(user.groups) == ["admins", "parent-group", "some-group"]
        assert user.passwords == []
        assert user.public_keys == []
        assert user.enabled
        assert user.service_account is None
        assert user.metadata == {}

        permissions = [(p.permission, p.argument) for p in user.permissions]
        assert sorted(permissions) == sorted(
            [
                (GROUP_ADMIN, ""),
                (USER_ADMIN, ""),
                ("some-permission", "one"),
                ("some-permission", "two"),
            ]
        )
