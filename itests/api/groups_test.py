from __future__ import annotations

from typing import TYPE_CHECKING

from groupy.client import Groupy

from itests.setup import api_server

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from tests.setup import SetupTest


def create_graph(setup: SetupTest) -> None:
    """Create a simple graph structure with some nesting and permissions."""
    setup.create_group("team-sre", email="team-sre@a.co")
    setup.add_user_to_group("gary@a.co", "team-sre", role="owner")
    setup.add_user_to_group("zay@a.co", "team-sre")
    setup.add_user_to_group("zorkian@a.co", "team-sre")
    setup.grant_permission_to_group("ssh", "*", "team-sre")
    setup.grant_permission_to_group("team-sre", "*", "team-sre")
    setup.add_group_to_group("team-sre", "serving-team")
    setup.add_user_to_group("zorkian@a.co", "serving-team", role="owner")
    setup.create_permission("audited", audited=True)
    setup.grant_permission_to_group("audited", "", "serving-team")
    setup.add_group_to_group("serving-team", "team-infra")
    setup.add_user_to_group("gary@a.co", "team-infra", role="owner")
    setup.grant_permission_to_group("sudo", "shell", "team-infra")
    setup.add_group_to_group("serving-team", "all-teams")
    setup.add_user_to_group("testuser@a.co", "all-teams", role="owner")


def test_get_groups(tmpdir: LocalPath, setup: SetupTest) -> None:
    with setup.transaction():
        create_graph(setup)

    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        assert sorted(api_client.groups) == ["all-teams", "serving-team", "team-infra", "team-sre"]


def test_get_group(tmpdir: LocalPath, setup: SetupTest) -> None:
    with setup.transaction():
        create_graph(setup)

    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)

        group = api_client.groups.get("team-sre")
        assert sorted(group.groups) == ["all-teams", "serving-team", "team-infra"]
        assert sorted(group.users) == ["gary@a.co", "zay@a.co", "zorkian@a.co"]
        assert group.subgroups == {}
        assert group.audited
        assert group.contacts == {"email": "team-sre@a.co"}

        permissions = [(p.permission, p.argument) for p in group.permissions]
        assert sorted(permissions) == [
            ("audited", ""),
            ("ssh", "*"),
            ("sudo", "shell"),
            ("team-sre", "*"),
        ]

        group = api_client.groups.get("serving-team")
        assert sorted(group.subgroups) == ["team-sre"]
