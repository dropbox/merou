import crypt
import json
import hashlib

from urllib import urlencode

import pytest

from fixtures import api_app as app  # noqa
from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from grouper.constants import USER_METADATA_SHELL_KEY
from grouper.models.counter import Counter
from grouper.models.permission import Permission
from grouper.models.user_token import UserToken
from grouper.user_metadata import get_user_metadata_by_key, set_user_metadata
from grouper.user_password import add_new_user_password, delete_user_password, user_passwords
from grouper.user_token import add_new_user_token, disable_user_token
from url_util import url
from util import grant_permission


@pytest.mark.gen_test
def test_users(users, http_client, base_url):
    api_url = url(base_url, '/users')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    users_wo_role = sorted((u for u in users if u != u"role@a.co"))

    print 'user_wo_role={}'.format(users_wo_role)
    print 'res={}'.format(sorted(body["data"]["users"]))
    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["users"]) == users_wo_role

    # TODO: test cutoff


@pytest.mark.gen_test
def test_service_accounts(users, http_client, base_url):
    api_url = url(base_url, '/service_accounts')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    service_accounts = sorted([user.name for user in users.values() if user.role_user])

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["service_accounts"]) == service_accounts


@pytest.mark.gen_test
def test_usertokens(users, session, http_client, base_url):
    user = users["zorkian@a.co"]
    tok, secret = add_new_user_token(session, UserToken(user=user, name="Foo"))
    session.commit()

    api_url = url(base_url, '/token/validate')

    # Completely bogus input
    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': 'invalid'}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 1

    valid_token = str(tok) + ":" + secret

    # Valid token
    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': valid_token}))
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

    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': token_with_bad_secret}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 4

    # Token with the token name frobbed to be something invalid
    token_with_bad_name = str(tok) + "z:" + secret

    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': token_with_bad_name}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 2

    # Token with the user frobbed to be something invalid
    token_with_bad_user = "z" + str(tok) + ":" + secret

    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': token_with_bad_user}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 2

    # Token with the user changed to another valid, but wrong user
    token_with_wrong_user = "oliver@a.co/" + tok.name + ":" + secret

    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': token_with_wrong_user}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 2

    # Disabled, but otherwise valid token
    disable_user_token(session, tok)
    session.commit()

    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': valid_token}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 3



@pytest.mark.gen_test
def test_permissions(permissions, http_client, base_url, session, graph):
    api_url = url(base_url, '/permissions')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["permissions"]) == sorted(permissions)

    api_url = url(base_url, '/permissions/{}'.format("team-sre"))
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"


@pytest.mark.gen_test
def test_groups(groups, http_client, base_url):
    api_url = url(base_url, '/groups')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["groups"]) == sorted(groups)

    # TODO: test cutoff


@pytest.mark.gen_test
def test_groups_email(groups, session, graph, http_client, base_url):
    expected_address = "sad-team@example.com"
    sad = groups['sad-team']
    sad.email_address = expected_address
    session.commit()
    Counter.incr(session, "updates")
    graph.update_from_db(session)

    api_url = url(base_url, '/groups/{}'.format(sad.name))
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert body["data"]["group"]["contacts"]["email"] == expected_address


@pytest.mark.gen_test
def test_shell(session, users, http_client, base_url, graph):
    user = users['zorkian@a.co']
    assert not get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY)

    set_user_metadata(session, user.id, USER_METADATA_SHELL_KEY, "/bin/bash")
    graph.update_from_db(session)

    fe_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(fe_url)
    assert resp.code == 200
    body = json.loads(resp.body)
    assert body["data"]["user"]["metadata"] != [], "There should be metadata"
    assert len(body["data"]["user"]["metadata"]) == 1, "There should only be 1 metadata!"
    assert body["data"]["user"]["metadata"][0]["data_key"] == "shell", "There should only be 1 metadata!"
    assert body["data"]["user"]["metadata"][0]["data_value"] == "/bin/bash", "The shell should be set to the correct value"

    set_user_metadata(session, user.id, USER_METADATA_SHELL_KEY, "/bin/zsh")
    graph.update_from_db(session)

    fe_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(fe_url)
    assert resp.code == 200
    body = json.loads(resp.body)
    assert body["data"]["user"]["metadata"] != [], "There should be metadata"
    assert body["data"]["user"]["metadata"][0]["data_key"] == "shell", "There should only be 1 metadata!"
    assert body["data"]["user"]["metadata"][0]["data_value"] == "/bin/zsh", "The shell should be set to the correct value"
    assert len(body["data"]["user"]["metadata"]) == 1, "There should only be 1 metadata!"

@pytest.mark.gen_test
def test_passwords_api(session, users, http_client, base_url, graph):
    user = users['zorkian@a.co']
    TEST_PASSWORD = "test_password_please_ignore"

    add_new_user_password(session, "test", TEST_PASSWORD, user.id)
    assert len(user_passwords(session, user)) == 1, "The user should only have a single password"

    graph.update_from_db(session)
    c = Counter.get(session, name="updates")
    api_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    assert body["checkpoint"] == c.count, "The API response is not up to date"
    assert body["data"]["user"]["passwords"] != [], "The user should not have an empty passwords field"
    assert body["data"]["user"]["passwords"][0]["name"] == "test", "The password should have the same name"
    assert body["data"]["user"]["passwords"][0]["func"] == "crypt(3)-$6$", "This test does not support any hash functions other than crypt(3)-$6$"
    assert body["data"]["user"]["passwords"][0]["hash"] == crypt.crypt(TEST_PASSWORD, body["data"]["user"]["passwords"][0]["salt"]), "The hash should be the same as hashing the password and the salt together using the hashing function"
    assert body["data"]["user"]["passwords"][0]["hash"] != crypt.crypt("hello", body["data"]["user"]["passwords"][0]["salt"]), "The hash should not be the same as hashing the wrong password and the salt together using the hashing function"

    delete_user_password(session, "test", user.id)
    c = Counter.get(session, name="updates")
    graph.update_from_db(session)
    api_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    assert body["checkpoint"] == c.count, "The API response is not up to date"
    assert body["data"]["user"]["passwords"] == [], "The user should not have any passwords"
