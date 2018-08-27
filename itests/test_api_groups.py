from fixtures import *  # noqa: F401
from tests.fixtures import *  # noqa: F401


def test_get_groups(api_client, groups):  # noqa: F811
    api_groups = list(api_client.groups)
    assert sorted(api_groups) == sorted(groups)


def test_get_group(api_client):  # noqa: F811
    group = api_client.groups.get("team-sre")
    assert sorted(group.groups) == ["all-teams", "serving-team", "team-infra"]
    assert sorted(group.users) == ["gary@a.co", "zay@a.co", "zorkian@a.co"]
    assert group.subgroups == {}

    perms = [(p.permission, p.argument) for p in group.permissions]
    assert sorted(perms) == [("audited", ""), ("ssh", "*"), ("sudo", "shell"), ("team-sre", "*")]

    assert group.audited
    assert group.contacts == {"email": "team-sre@a.co"}
