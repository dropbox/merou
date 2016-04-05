import json
from urllib import urlencode

import pytest
from tornado.httpclient import HTTPError

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from grouper import public_key
from grouper.model_soup import User
from url_util import url


@pytest.mark.gen_test
def test_auth(users, http_client, base_url):
    # no 'auth' present
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(base_url)

    # invalid user
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(base_url, headers={'X-Grouper-User': 'nobody'})

    # valid user
    resp = yield http_client.fetch(base_url, headers={'X-Grouper-User': 'zorkian@a.co'})
    assert resp.code == 200


@pytest.mark.gen_test
def test_public_key(session, users, http_client, base_url):
    user = users['zorkian@a.co']
    assert not user.my_public_keys()

    good_key = ('ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDCUQeasspT/etEJR2WUoR+h2sMOQYbJgr0Q'
            'E+J8p97gEhmz107KWZ+3mbOwyIFzfWBcJZCEg9wy5Paj+YxbGONqbpXAhPdVQ2TLgxr41bNXvbcR'
            'AxZC+Q12UZywR4Klb2kungKz4qkcmSZzouaKK12UxzGB3xQ0N+3osKFj3xA1+B6HqrVreU19XdVo'
            'AJh0xLZwhw17/NDM+dAcEdMZ9V89KyjwjraXtOVfFhQF0EDF0ame8d6UkayGrAiXC2He0P2Cja+J'
            '371P27AlNLHFJij8WGxvcGGSeAxMLoVSDOOllLCYH5UieV8mNpX1kNe2LeA58ciZb0AXHaipSmCH'
            'gh/ some-comment')

    bad_key = 'ssh-rsa AAAblahblahkey some-comment'

    # add it
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': good_key}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    # add bad key -- shouldn't add
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': bad_key}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = User.get(session, name=user.username)
    keys = user.my_public_keys()
    assert len(keys) == 1
    assert keys[0].public_key == good_key

    # delete it
    fe_url = url(base_url, '/users/{}/public-key/{}/delete'.format(user.username, keys[0].id))
    resp = yield http_client.fetch(fe_url, method="POST", body='',
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = User.get(session, name=user.username)
    assert not user.my_public_keys()

@pytest.mark.gen_test
def test_usertokens(session, users, http_client, base_url):
    user = users['zorkian@a.co']
    assert len(user.tokens) == 0

    # Add token
    fe_url = url(base_url, '/users/{}/tokens/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'name': 'myFoobarToken'}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    # Verify add
    fe_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="GET",
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200
    assert "Added token: myFoobarToken" in resp.body

    # Disable token
    fe_url = url(base_url, '/users/{}/tokens/1/disable'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body="",
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    # Verify disable
    fe_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="GET",
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200
    assert "Disabled token: myFoobarToken" in resp.body
