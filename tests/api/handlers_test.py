import crypt
import csv
import json
import time
from io import StringIO
from urllib.parse import urlencode

import pytest
from mock import Mock
from tornado.httpclient import HTTPError

from grouper.constants import USER_METADATA_GITHUB_USERNAME_KEY, USER_METADATA_SHELL_KEY
from grouper.models.counter import Counter
from grouper.models.service_account import ServiceAccount
from grouper.models.user_token import UserToken
from grouper.permissions import get_permission, grant_permission_to_service_account
from grouper.plugin import get_plugin_proxy
from grouper.public_key import add_public_key
from grouper.user_metadata import get_user_metadata_by_key, set_user_metadata
from grouper.user_password import add_new_user_password, delete_user_password, user_passwords
from grouper.user_token import add_new_user_token, disable_user_token
from tests.constants import SSH_KEY_1
from tests.fixtures import (  # noqa: F401
    api_app as app,
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)
from tests.url_util import url


@pytest.mark.gen_test
def test_health(session, http_client, base_url):  # noqa: F811
    health_url = url(base_url, "/debug/health")
    resp = yield http_client.fetch(health_url)
    assert resp.code == 200


@pytest.mark.gen_test
def test_users(users, http_client, base_url):  # noqa: F811
    all_users = sorted(list(users.keys()) + ["service@a.co"])
    users_wo_role = sorted([u for u in users if u != "role@a.co"])

    api_url = url(base_url, "/users")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["users"]) == users_wo_role

    api_url = url(base_url, "/users?include_role_users=yes")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["users"]) == all_users


@pytest.mark.gen_test
def test_multi_users(users, http_client, base_url):  # noqa: F811
    def make_url(*usernames):
        query_args = urlencode({"username": usernames}, doseq=True)

        return url(base_url, "/multi/users?{}".format(query_args))

    # Test case when no usernames are provided
    api_url = make_url()
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    # Service Accounts should be included
    assert sorted(list(body["data"].keys())) == sorted(list(users.keys()) + ["service@a.co"])

    # Test case when only valid usernames are provided
    api_url = make_url("tyleromeara@a.co", "gary@a.co", "role@a.co")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    # Service Accounts should be included
    assert sorted(list(body["data"].keys())) == ["gary@a.co", "role@a.co", "tyleromeara@a.co"]
    # Verify that we return the same data as the single user endpoint
    for username, data in body["data"].items():
        r = yield http_client.fetch(url(base_url, "/users/{}".format(username)))
        rbody = json.loads(r.body)
        assert data == rbody["data"]

    # Ensure that nonexistent usernames are ignored
    api_url = make_url("tyleromeara@a.co", "gary@a.co", "doesnotexist@a.co")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(list(body["data"].keys())) == ["gary@a.co", "tyleromeara@a.co"]

    # Test when only nonexistent usernames are given
    api_url = make_url("doesnotexist@a.co", "doesnotexist2@a.co")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(list(body["data"].keys())) == []


@pytest.mark.gen_test
def test_service_accounts(session, standard_graph, users, http_client, base_url):  # noqa: F811
    api_url = url(base_url, "/service_accounts")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["service_accounts"]) == sorted(
        [u.name for u in users.values() if u.role_user] + ["service@a.co"]
    )

    # Retrieve a single service account and check its metadata.
    api_url = url(base_url, "/service_accounts/service@a.co")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    assert resp.code == 200
    assert body["status"] == "ok"
    data = body["data"]["user"]
    assert "service_account" in data
    assert data["service_account"]["description"] == "some service account"
    assert data["service_account"]["machine_set"] == "some machines"
    assert data["service_account"]["owner"] == "team-sre"
    assert body["data"]["permissions"] == []

    # Delegate a permission to the service account and check for it.
    service_account = ServiceAccount.get(session, name="service@a.co")
    permission = get_permission(session, "team-sre")
    grant_permission_to_service_account(session, service_account, permission, "*")
    standard_graph.update_from_db(session)
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    assert resp.code == 200
    assert body["status"] == "ok"
    perms = body["data"]["permissions"]
    assert perms[0]["permission"] == "team-sre"
    assert perms[0]["argument"] == "*"


@pytest.mark.gen_test
def test_usertokens(users, session, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]
    tok, secret = add_new_user_token(session, UserToken(user=user, name="Foo"))
    session.commit()

    api_url = url(base_url, "/token/validate")

    # Completely bogus input
    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({"token": "invalid"}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 1

    valid_token = str(tok) + ":" + secret

    # Valid token
    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({"token": valid_token}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert body["data"]["identity"] == str(tok)
    assert body["data"]["owner"] == user.username
    assert body["data"]["act_as_owner"]
    assert body["data"]["valid"]

    # Token with the last character changed to something invalid
    bad_char = "1" if secret[-1].isalpha() else "a"
    token_with_bad_secret = str(tok) + ":" + secret[:-1] + bad_char

    resp = yield http_client.fetch(
        api_url, method="POST", body=urlencode({"token": token_with_bad_secret})
    )
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 4

    # Token with the token name frobbed to be something invalid
    token_with_bad_name = str(tok) + "z:" + secret

    resp = yield http_client.fetch(
        api_url, method="POST", body=urlencode({"token": token_with_bad_name})
    )
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 2

    # Token with the user frobbed to be something invalid
    token_with_bad_user = "z" + str(tok) + ":" + secret

    resp = yield http_client.fetch(
        api_url, method="POST", body=urlencode({"token": token_with_bad_user})
    )
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 2

    # Token with the user changed to another valid, but wrong user
    token_with_wrong_user = "oliver@a.co/" + tok.name + ":" + secret

    resp = yield http_client.fetch(
        api_url, method="POST", body=urlencode({"token": token_with_wrong_user})
    )
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 2

    # Disabled, but otherwise valid token
    disable_user_token(session, tok)
    session.commit()

    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({"token": valid_token}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 3


@pytest.mark.gen_test
def test_permissions(permissions, http_client, base_url, session, graph):  # noqa: F811
    api_url = url(base_url, "/permissions")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["permissions"]) == sorted(permissions)

    api_url = url(base_url, "/permissions/{}".format("team-sre"))
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"


@pytest.mark.gen_test
def test_groups(groups, http_client, base_url):  # noqa: F811
    api_url = url(base_url, "/groups")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["groups"]) == sorted(groups)


@pytest.mark.gen_test
def test_groups_email(groups, session, graph, http_client, base_url):  # noqa: F811
    expected_address = "sad-team@example.com"
    sad = groups["sad-team"]
    sad.email_address = expected_address
    session.commit()
    Counter.incr(session, "updates")
    graph.update_from_db(session)

    api_url = url(base_url, "/groups/{}".format(sad.name))
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert body["data"]["group"]["contacts"]["email"] == expected_address


@pytest.mark.gen_test
def test_shell(session, users, http_client, base_url, graph):  # noqa: F811
    user = users["zorkian@a.co"]
    assert not get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY)

    set_user_metadata(session, user.id, USER_METADATA_SHELL_KEY, "/bin/bash")
    graph.update_from_db(session)

    fe_url = url(base_url, "/users/{}".format(user.username))
    resp = yield http_client.fetch(fe_url)
    assert resp.code == 200
    body = json.loads(resp.body)
    assert body["data"]["user"]["metadata"] != [], "There should be metadata"
    assert len(body["data"]["user"]["metadata"]) == 1, "There should only be 1 metadata!"
    assert (
        body["data"]["user"]["metadata"][0]["data_key"] == "shell"
    ), "There should only be 1 metadata!"
    assert (
        body["data"]["user"]["metadata"][0]["data_value"] == "/bin/bash"
    ), "The shell should be set to the correct value"

    set_user_metadata(session, user.id, USER_METADATA_SHELL_KEY, "/bin/zsh")
    graph.update_from_db(session)

    fe_url = url(base_url, "/users/{}".format(user.username))
    resp = yield http_client.fetch(fe_url)
    assert resp.code == 200
    body = json.loads(resp.body)
    assert body["data"]["user"]["metadata"] != [], "There should be metadata"
    assert (
        body["data"]["user"]["metadata"][0]["data_key"] == "shell"
    ), "There should only be 1 metadata!"
    assert (
        body["data"]["user"]["metadata"][0]["data_value"] == "/bin/zsh"
    ), "The shell should be set to the correct value"
    assert len(body["data"]["user"]["metadata"]) == 1, "There should only be 1 metadata!"


@pytest.mark.gen_test
def test_github_username(session, users, http_client, base_url, graph):  # noqa: F811
    user = users["zorkian@a.co"]
    assert get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY) is None

    set_user_metadata(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY, "zorkian-on-gh")
    graph.update_from_db(session)
    fe_url = url(base_url, "/users/{}".format(user.username))
    resp = yield http_client.fetch(fe_url)
    assert resp.code == 200
    body = json.loads(resp.body)
    [metadata] = body["data"]["user"]["metadata"]
    assert metadata["data_key"] == "github_username"
    assert metadata["data_value"] == "zorkian-on-gh"

    set_user_metadata(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY, None)
    graph.update_from_db(session)
    fe_url = url(base_url, "/users/{}".format(user.username))
    resp = yield http_client.fetch(fe_url)
    assert resp.code == 200
    body = json.loads(resp.body)
    assert body["data"]["user"]["metadata"] == []


@pytest.mark.gen_test
def test_passwords_api(session, users, http_client, base_url, graph):  # noqa: F811
    user = users["zorkian@a.co"]
    TEST_PASSWORD = "test_password_please_ignore"

    add_new_user_password(session, "test", TEST_PASSWORD, user.id)
    assert len(user_passwords(session, user)) == 1, "The user should only have a single password"

    graph.update_from_db(session)
    c = Counter.get(session, name="updates")
    api_url = url(base_url, "/users/{}".format(user.username))
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    assert body["checkpoint"] == c.count, "The API response is not up to date"
    assert (
        body["data"]["user"]["passwords"] != []
    ), "The user should not have an empty passwords field"
    assert (
        body["data"]["user"]["passwords"][0]["name"] == "test"
    ), "The password should have the same name"
    assert (
        body["data"]["user"]["passwords"][0]["func"] == "crypt(3)-$6$"
    ), "This test does not support any hash functions other than crypt(3)-$6$"
    assert body["data"]["user"]["passwords"][0]["hash"] == crypt.crypt(
        TEST_PASSWORD, body["data"]["user"]["passwords"][0]["salt"]
    ), (
        "The hash should be the same as hashing the password and the salt together using the"
        " hashing function"
    )
    assert body["data"]["user"]["passwords"][0]["hash"] != crypt.crypt(
        "hello", body["data"]["user"]["passwords"][0]["salt"]
    ), (
        "The hash should not be the same as hashing the wrong password and the salt together"
        " using the hashing function"
    )

    delete_user_password(session, "test", user.id)
    c = Counter.get(session, name="updates")
    graph.update_from_db(session)
    api_url = url(base_url, "/users/{}".format(user.username))
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    assert body["checkpoint"] == c.count, "The API response is not up to date"
    assert body["data"]["user"]["passwords"] == [], "The user should not have any passwords"


@pytest.mark.gen_test
def test_public_keys(session, users, http_client, base_url):  # noqa: F811
    user = users["cbguder@a.co"]

    add_public_key(session, user, SSH_KEY_1)

    api_url = url(base_url, "/public-keys")
    resp = yield http_client.fetch(api_url)

    body_io = StringIO(resp.body.decode())
    csv_reader = csv.DictReader(body_io)
    rows = list(csv_reader)

    assert len(rows) == 1
    assert rows[0]["username"] == "cbguder@a.co"
    assert rows[0]["fingerprint"] == "6f:c4:6b:f1:d7:29:b0:14:41:52:3c:83:fb:53:a5:85"
    assert rows[0]["fingerprint_sha256"] == "x9HI/CF9Aoi7Mh7bfDMi0FzcqfIU4FEup6dfYh3b1w0"
    assert rows[0]["comment"] == "some-comment"


@pytest.mark.gen_test
def test_request_logging(session, users, http_client, base_url):  # noqa: F811
    """Test that the api request handlers properly log stats"""
    mock_plugin = Mock()
    get_plugin_proxy().add_plugin(mock_plugin)

    user = users["zorkian@a.co"]
    fe_url = url(base_url, "/users/{}".format(user.username))
    start_time = time.time()
    resp = yield http_client.fetch(fe_url, method="GET", headers={"X-Grouper-User": user.username})
    duration_ms = (time.time() - start_time) * 1000
    assert resp.code == 200
    assert mock_plugin.log_request.call_count == 1
    assert mock_plugin.log_request.call_args_list[0][0][0] == "Users"
    assert mock_plugin.log_request.call_args_list[0][0][1] == 200
    # the reported value should be within 1s of our own observation
    assert abs(mock_plugin.log_request.call_args_list[0][0][2] - duration_ms) <= 1000
    assert mock_plugin.log_request.call_args_list[0][0][3].path == "/users/zorkian@a.co"

    mock_plugin.log_request.reset_mock()
    start_time = time.time()
    with pytest.raises(HTTPError):
        fe_url = url(base_url, "/groups/{}".format("does-not-exist"))
        resp = yield http_client.fetch(
            fe_url, method="GET", headers={"X-Grouper-User": user.username}
        )
    duration_ms = (time.time() - start_time) * 1000
    assert mock_plugin.log_request.call_count == 1
    assert mock_plugin.log_request.call_args_list[0][0][0] == "Groups"
    assert mock_plugin.log_request.call_args_list[0][0][1] == 404
    # the reported value should be within 1s of our own observation
    assert abs(mock_plugin.log_request.call_args_list[0][0][2] - duration_ms) <= 1000
    assert mock_plugin.log_request.call_args_list[0][0][3].path == "/groups/does-not-exist"
