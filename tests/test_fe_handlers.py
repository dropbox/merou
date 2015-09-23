import json

import pytest
from tornado.httpclient import HTTPError

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from url_util import url


@pytest.mark.gen_test
def test_auth(users, http_client, base_url):
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(base_url)

        # TODO(herb): have a better story around UI testing
        #resp = yield http_client.fetch(base_url, headers={'X-Grouper-User': 'zay'})
