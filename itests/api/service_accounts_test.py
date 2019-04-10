from six import iteritems

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


def test_get_service_accounts(api_client, users, service_accounts):  # noqa: F811
    role_users = [username for username, u in iteritems(users) if u.role_user]
    assert len(role_users) > 0

    expected = role_users + list(service_accounts.keys())

    api_service_accounts = list(api_client.service_accounts)
    assert sorted(api_service_accounts) == sorted(expected)


def test_get_service_account(api_client):  # noqa: F811
    service_account = api_client.service_accounts.get("service@a.co")
    assert service_account.groups == {}
    assert service_account.passwords == []
    assert service_account.public_keys == []
    assert service_account.enabled
    assert service_account.service_account == {
        "description": "some service account",
        "machine_set": "some machines",
        "owner": "team-sre",
    }
    assert service_account.permissions == []
    assert service_account.metadata == {}


def test_get_role_user(api_client):  # noqa: F811
    role_user = api_client.service_accounts.get("role@a.co")
    assert role_user.groups == {}
    assert role_user.passwords == []
    assert role_user.public_keys == []
    assert role_user.enabled
    assert role_user.service_account is None
    assert role_user.permissions == []
    assert role_user.metadata == {}
