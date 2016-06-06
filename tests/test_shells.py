import json
from urllib import urlencode
from mock import patch

import pytest
from tornado.httpclient import HTTPError

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from grouper import public_key
from grouper.model_soup import User, Request, AsyncNotification
from grouper.constants import SHELL_MD_KEY
from url_util import url


@pytest.mark.gen_test
def test_shell(session, users, http_client, base_url):
    user = users['zorkian@a.co']
    assert not user.get_metadata(SHELL_MD_KEY)

    fe_url = url(base_url, '/users/{}/shell'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'shell': "/bin/bash"}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = User.get(session, name=user.username)

    assert user.get_metadata(SHELL_MD_KEY) is not None, "The user should have shell metadata"
    assert user.get_metadata(SHELL_MD_KEY).data_value == "/bin/bash"

    fe_url = url(base_url, '/users/{}/shell'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'shell': "/bin/fish"}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = User.get(session, name=user.username)

    assert user.get_metadata(SHELL_MD_KEY) is not None, "The user should have shell metadata"
    assert user.get_metadata(SHELL_MD_KEY).data_value == "/bin/bash"

    fe_url = url(base_url, '/users/{}/shell'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'shell': "/bin/zsh"}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = User.get(session, name=user.username)

    assert user.get_metadata(SHELL_MD_KEY) is not None, "The user should have shell metadata"
    assert user.get_metadata(SHELL_MD_KEY).data_value == "/bin/zsh"
