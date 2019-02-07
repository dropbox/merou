from itests.fixtures import api_client, async_api_server  # noqa: F401
from tests.fixtures import (  # noqa: F401
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)


def test_get_permissions(api_client, permissions):  # noqa: F811
    api_permissions = list(api_client.permissions)
    assert sorted(api_permissions) == sorted(permissions)


def test_get_permission(api_client):  # noqa: F811
    permission = api_client.permissions.get("ssh")
    assert sorted(permission.groups) == ["sad-team", "team-sre", "tech-ops"]
