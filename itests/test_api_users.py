from fixtures import *  # noqa: F401
from tests.fixtures import *  # noqa: F401


def test_get_users(api_client, users):  # noqa: F811
    real_users = [username for username, u in users.iteritems() if not u.role_user]
    assert len(real_users) > 0

    api_users = list(api_client.users)
    assert sorted(api_users) == sorted(real_users)


def test_get_user(api_client):  # noqa: F811
    user = api_client.users.get("cbguder@a.co")
    assert sorted(user.groups) == ["group-admins", "user-admins"]
    assert user.passwords == []
    assert user.public_keys == []
    assert user.enabled
    assert user.service_account is None

    perms = [(p.permission, p.argument) for p in user.permissions]
    assert sorted(perms) == [("grouper.admin.groups", ""), ("grouper.admin.users", "")]

    assert user.metadata == {}
