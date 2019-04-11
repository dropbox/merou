from six import iteritems

from grouper.constants import GROUP_ADMIN, PERMISSION_ADMIN, USER_ADMIN
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


def test_get_users(api_client, users):  # noqa: F811
    real_users = [username for username, u in iteritems(users) if not u.role_user]
    assert len(real_users) > 0

    api_users = list(api_client.users)
    assert sorted(api_users) == sorted(real_users)


def test_get_user(api_client):  # noqa: F811
    user = api_client.users.get("cbguder@a.co")
    assert sorted(user.groups) == ["group-admins", "permission-admins", "user-admins"]
    assert user.passwords == []
    assert user.public_keys == []
    assert user.enabled
    assert user.service_account is None

    perms = [(p.permission, p.argument) for p in user.permissions]
    assert sorted(perms) == [(GROUP_ADMIN, ""), (PERMISSION_ADMIN, ""), (USER_ADMIN, "")]

    assert user.metadata == {}
