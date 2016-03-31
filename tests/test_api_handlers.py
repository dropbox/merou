import json

from urllib import urlencode

import pytest

from fixtures import api_app as app  # noqa
from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from grouper.models.user_token import UserToken
from grouper.user_token import add_new_user_token, disable_user_token
from url_util import url


@pytest.mark.gen_test
def test_users(users, http_client, base_url):
    # without role users
    api_url = url(base_url, '/users')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    users_wo_role = sorted((u for u in users if u != u"role@a.co"))

    print 'user_wo_role={}'.format(users_wo_role)
    print 'res={}'.format(sorted(body["data"]["users"]))
    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["users"]) == users_wo_role

    # with role users
    api_url = url(base_url, '/users', {'include_role_users': 'yes'})
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    users_w_role = sorted(users)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["users"]) == users_w_role

    # TODO: test cutoff

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
def test_permissions(permissions, http_client, base_url):
    api_url = url(base_url, '/permissions')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["permissions"]) == sorted(permissions)


@pytest.mark.gen_test
def test_groups(groups, http_client, base_url):
    api_url = url(base_url, '/groups')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["groups"]) == sorted(groups)

    # TODO: test cutoff
