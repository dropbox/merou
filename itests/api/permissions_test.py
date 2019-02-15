from typing import TYPE_CHECKING

from groupy.client import Groupy

from itests.setup import api_server

if TYPE_CHECKING:
    from py.path import LocalPath
    from tests.setup import SetupTest


def test_get_permissions(tmpdir, setup):
    # type: (LocalPath, SetupTest) -> None
    setup.create_permission("some-permission")
    setup.create_permission("another-permission")
    setup.commit()
    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        assert sorted(api_client.permissions) == ["another-permission", "some-permission"]


def test_get_permission(tmpdir, setup):
    # type: (LocalPath, SetupTest) -> None
    setup.grant_permission_to_group("sad-team", "ssh", "foo")
    setup.grant_permission_to_group("team-sre", "ssh", "bar")
    setup.grant_permission_to_group("tech-ops", "ssh", "*")
    setup.commit()
    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        permission = api_client.permissions.get("ssh")
        assert sorted(permission.groups) == ["sad-team", "team-sre", "tech-ops"]
