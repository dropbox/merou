from datetime import datetime
from time import time
from typing import TYPE_CHECKING

import pytest

from grouper.entities.group import GroupJoinPolicy
from grouper.graph import NoSuchGroup, NoSuchUser
from grouper.plugin.base import BasePlugin

if TYPE_CHECKING:
    from tests.setup import SetupTest


def build_test_graph(setup):
    # type: (SetupTest) -> None
    """Build a relatively complex test graph.

    +-----------------------+
    |                       |
    |  team-sre             |
    |    * gary (o)         +---------------------------------+
    |    * zay              |                                 |
    |    * zorkian          |                                 |
    |    * service (s)      |                     +-----------v-----------+
    |                       |                     |                       |
    +-----------------------+                     |  serving-team         |
    +-----------------------+           +--------->    * zorkian (o)      |
    |                       |           |         |                       |
    |  tech-ops             |           |         +-----------+-----------+
    |    * zay (o)          |           |                     |
    |    * gary             +-----------+                     |
    |    * figurehead (np)  |                                 |
    |                       |                                 |
    +-----------------------+                                 |
    +-----------------------+                     +-----------v-----------+
    |                       |                     |                       |
    |  security-team        |                     |  team-infra           |
    |    * oliver (o)       +--------------------->    * gary (o)         |
    |    * figurehead       |                     |                       |
    |                       |                     +-----------+-----------+
    +-----------------------+                                 |
    +-----------------------+                     +-----------v-----------+
    |                       |                     |                       |
    |  sad-team             |                     |  all-teams            |
    |    * zorkian (o)      |                     |    * testuser (o)     |
    |    * oliver           |                     |                       |
    |                       |                     +-----------------------+
    +-----------------------+

    Arrows denote that the group at the tail of the arrow is a member of the group at the head of
    the arrow.  (o) for owners, (np) for non-permissioned owners, (s) for service accounts.
    """
    with setup.transaction():
        setup.add_user_to_group("testuser@a.co", "all-teams", role="owner")

        setup.add_user_to_group("gary@a.co", "team-infra", role="owner")
        setup.add_group_to_group("team-infra", "all-teams")
        setup.grant_permission_to_group("sudo", "shell", "team-infra")

        setup.add_user_to_group("zorkian@a.co", "serving-team", role="owner")
        setup.add_group_to_group("serving-team", "team-infra")
        setup.create_permission("audited", "An audited permission", audited=True)
        setup.grant_permission_to_group("audited", "", "serving-team")

        setup.add_user_to_group("gary@a.co", "team-sre", role="owner")
        setup.add_user_to_group("zay@a.co", "team-sre")
        setup.add_user_to_group("zorkian@a.co", "team-sre")
        setup.create_service_account(
            "service@svc.localhost", "team-sre", "Some service account", "owner=team-sre"
        )
        setup.add_group_to_group("team-sre", "serving-team")
        setup.grant_permission_to_group("ssh", "*", "team-sre")
        setup.grant_permission_to_group("team-sre", "*", "team-sre")
        setup.grant_permission_to_service_account("team-sre", "*", "service@svc.localhost")

        setup.add_user_to_group("zay@a.co", "tech-ops", role="owner")
        setup.add_user_to_group("gary@a.co", "tech-ops")
        setup.add_user_to_group("figurehead@a.co", "tech-ops", role="np-owner")
        setup.add_group_to_group("tech-ops", "serving-team")
        setup.grant_permission_to_group("ssh", "shell", "tech-ops")

        setup.add_user_to_group("oliver@a.co", "security-team", role="owner")
        setup.add_user_to_group("figurehead@a.co", "security-team")
        setup.add_group_to_group("security-team", "team-infra")

        setup.add_user_to_group("zorkian@a.co", "sad-team", role="owner")
        setup.add_user_to_group("oliver@a.co", "sad-team")
        setup.grant_permission_to_group("owner", "sad-team", "sad-team")


def test_get_permissions(setup):
    # type: (SetupTest) -> None
    build_test_graph(setup)
    permissions = setup.graph.get_permissions()
    permission_names = [p.name for p in permissions]
    assert sorted(permission_names) == ["audited", "owner", "ssh", "sudo", "team-sre"]
    permissions = setup.graph.get_permissions(audited=True)
    assert all([p.audited == True for p in permissions])
    permission_names = [p.name for p in permissions]
    assert sorted(permission_names) == ["audited"]


def test_get_permissions_data(setup):
    # type: (SetupTest) -> None
    """Test some of the other permission fields not exercised by the sample graph."""
    early_date = datetime.utcfromtimestamp(1)
    now = datetime.utcfromtimestamp(int(time()))
    with setup.transaction():
        setup.create_permission("one", "Description", created_on=early_date)
        setup.create_permission("disabled", "", enabled=False, created_on=now)
        setup.create_permission("audited", "Audited permission", audited=True, created_on=now)

    permission = {p.name: p for p in setup.graph.get_permissions()}
    assert "disabled" not in permission
    assert permission["one"].description == "Description"
    assert not permission["one"].audited
    assert permission["one"].created_on == early_date
    assert permission["audited"].description == "Audited permission"
    assert permission["audited"].audited
    assert permission["audited"].created_on == now

    permissions = [p.name for p in setup.graph.get_permissions(audited=True)]
    assert permissions == ["audited"]


def test_get_permission_details(setup):
    # type: (SetupTest) -> None
    build_test_graph(setup)

    details = setup.graph.get_permission_details("sudo")
    groups_with_sudo = details["groups"].keys()
    assert sorted(groups_with_sudo) == [
        "security-team",
        "serving-team",
        "team-infra",
        "team-sre",
        "tech-ops",
    ]
    for group in groups_with_sudo:
        for permission_data in details["groups"][group]["permissions"]:
            assert permission_data["permission"] == "sudo"
            assert permission_data["argument"] == "shell"
    assert not details["service_accounts"]

    details = setup.graph.get_permission_details("team-sre")
    service_accounts_with_sudo = details["service_accounts"].keys()
    assert sorted(service_accounts_with_sudo) == ["service@svc.localhost"]
    for service in service_accounts_with_sudo:
        for permission_data in details["service_accounts"][service]["permissions"]:
            assert permission_data["permission"] == "team-sre"
            assert permission_data["argument"] == "*"


def test_get_disabled_groups(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_group("sad-team", "Some group", join_policy=GroupJoinPolicy.CAN_JOIN)
    assert setup.graph.get_disabled_groups() == []
    with setup.transaction():
        setup.disable_group("sad-team")
    disabled_groups = setup.graph.get_disabled_groups()
    assert len(disabled_groups) == 1
    disabled_group = disabled_groups[0]
    assert disabled_group.name == "sad-team"
    assert disabled_group.description == "Some group"
    assert disabled_group.join_policy == GroupJoinPolicy.CAN_JOIN
    assert not disabled_group.enabled
    assert not disabled_group.is_role_user


def test_get_groups(setup):
    # type: (SetupTest) -> None
    build_test_graph(setup)

    groups = setup.graph.get_groups()
    group_names = [g.name for g in groups]
    assert sorted(group_names) == [
        "all-teams",
        "sad-team",
        "security-team",
        "serving-team",
        "team-infra",
        "team-sre",
        "tech-ops",
    ]
    for group in groups:
        assert group.description == ""
        assert group.join_policy == GroupJoinPolicy.CAN_ASK
        assert group.enabled
        assert not group.is_role_user

    groups = setup.graph.get_groups(audited=True)
    group_names = [g.name for g in groups]
    assert sorted(group_names) == ["serving-team", "team-sre", "tech-ops"]
    groups = setup.graph.get_groups(directly_audited=True)
    group_names = [g.name for g in groups]
    assert sorted(group_names) == ["serving-team"]


def test_get_groups_role_user(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        setup.create_group("some-group", "")
        setup.create_role_user("role-user@a.co")
        setup.create_group("not-role-user@a.co")
        setup.create_user("not-role-user@a.co")

    groups = {g.name: g for g in setup.graph.get_groups()}
    assert not groups["some-group"].is_role_user
    assert groups["role-user@a.co"].is_role_user
    assert not groups["not-role-user@a.co"].is_role_user


def test_get_group_details(setup):
    # type: (SetupTest) -> None
    build_test_graph(setup)

    with pytest.raises(NoSuchGroup):
        setup.graph.get_group_details("nonexistent")

    details = setup.graph.get_group_details("serving-team")
    assert sorted(details["groups"].keys()) == ["all-teams", "team-infra"]
    assert sorted(details["subgroups"].keys()) == ["team-sre", "tech-ops"]
    assert sorted(details["users"].keys()) == [
        "figurehead@a.co",
        "gary@a.co",
        "zay@a.co",
        "zorkian@a.co",
    ]
    assert details["audited"]
    user_details = details["users"]["zorkian@a.co"]
    assert user_details["name"] == "zorkian@a.co"
    assert user_details["distance"] == 1
    assert user_details["rolename"] == "owner"
    user_details = details["users"]["figurehead@a.co"]
    assert user_details["name"] == "figurehead@a.co"
    assert user_details["distance"] == 2
    assert user_details["rolename"] == "member"
    permissions = [(p["permission"], p["argument"]) for p in details["permissions"]]
    assert sorted(permissions) == [("audited", ""), ("sudo", "shell")]

    details = setup.graph.get_group_details("sad-team")
    assert sorted(details["groups"].keys()) == []
    assert sorted(details["subgroups"].keys()) == []
    assert sorted(details["users"].keys()) == ["oliver@a.co", "zorkian@a.co"]
    permissions = [(p["permission"], p["argument"]) for p in details["permissions"]]
    assert sorted(permissions) == [("owner", "sad-team")]


def test_get_user_details(setup):
    # type: (SetupTest) -> None
    build_test_graph(setup)

    with pytest.raises(NoSuchUser):
        setup.graph.get_user_details("nonexistent@a.co")

    details = setup.graph.get_user_details("figurehead@a.co")
    assert sorted(details["groups"].keys()) == [
        "all-teams",
        "security-team",
        "team-infra",
        "tech-ops",
    ]
    group_details = details["groups"]["tech-ops"]
    assert group_details["distance"] == 1
    assert group_details["rolename"] == "np-owner"
    group_details = details["groups"]["all-teams"]
    assert group_details["distance"] == 3
    assert group_details["rolename"] == "member"
    permissions = [(p["permission"], p["argument"]) for p in details["permissions"]]
    assert sorted(permissions) == [("sudo", "shell")]

    details = setup.graph.get_user_details("service@svc.localhost")
    assert not details["groups"]
    permissions = [(p["permission"], p["argument"]) for p in details["permissions"]]
    assert sorted(permissions) == [("team-sre", "*")]


class MockStats(BasePlugin):
    def __init__(self):
        # type: () -> None
        self.update_ms = 0.0

    def log_graph_update_duration(self, duration_ms):
        # type: (int) -> None
        self.update_ms = duration_ms


def test_graph_update_stats(setup):
    # type: (SetupTest) -> None
    """Test that update timings are logged by a graph update."""
    mock_stats = MockStats()
    setup.plugins.add_plugin(mock_stats)

    # Create a user and a group, which will trigger a graph update.
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    assert mock_stats.update_ms > 0.0
