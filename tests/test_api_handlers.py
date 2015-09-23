import json
import pytest

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import api_app as app  # noqa
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
