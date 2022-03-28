from typing import TYPE_CHECKING

from groupy.client import Groupy

from itests.setup import api_server

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from tests.setup import SetupTest


def test_get_permissions(tmpdir, setup):
    # type: (LocalPath, SetupTest) -> None
    with setup.transaction():
        setup.create_permission("some-permission")
        setup.create_permission("another-permission")
    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        assert sorted(api_client.permissions) == ["another-permission", "some-permission"]


def test_get_permission(tmpdir, setup):
    # type: (LocalPath, SetupTest) -> None
    with setup.transaction():
        setup.grant_permission_to_group("ssh", "foo", "sad-team")
        setup.grant_permission_to_group("ssh", "bar", "team-sre")
        setup.grant_permission_to_group("ssh", "*", "tech-ops")
    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        permission = api_client.permissions.get("ssh")
        assert sorted(permission.groups) == ["sad-team", "team-sre", "tech-ops"]
