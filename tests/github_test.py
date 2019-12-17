import io
import json
import operator
from urllib.parse import parse_qs, urlparse

import pytest
from tornado.concurrent import Future
from tornado.httpclient import HTTPError, HTTPResponse

from grouper.constants import USER_METADATA_GITHUB_USERNAME_KEY
from grouper.fe.settings import settings
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.plugin.proxy import PluginProxy
from grouper.user_metadata import get_user_metadata_by_key, set_user_metadata
from tests.fixtures import (  # noqa: F401
    fe_app as app,
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)
from tests.url_util import url


class FakeGitHubHttpClient:
    def __init__(self):
        self.requests = []

    def fetch(self, request):
        f = Future()
        resp = HTTPResponse(request, 200, buffer=io.BytesIO())
        f.set_result(resp)
        self.requests.append(request)
        if request.url == "https://github.com/login/oauth/access_token":
            resp.buffer.write(
                json.dumps({"access_token": "a-access-token", "token_type": "bearer"}).encode(
                    "utf-8"
                )
            )
        elif request.url == "https://api.github.com/user":
            resp.buffer.write(json.dumps({"login": "zorkian-on-gh"}).encode("utf-8"))
        else:
            raise AssertionError("unknown url: {!r}".format(request.url))
        return f


class SecretPlugin:
    def get_github_app_client_secret(self):
        return b"client-secret"


@pytest.mark.gen_test
def test_github(session, users, http_client, base_url, mocker):  # noqa: F811
    user = users["zorkian@a.co"]
    assert get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY) is None

    user = User.get(session, name=user.username)
    fe_url = url(base_url, "/github/link_begin/{}".format(user.id))
    mocker.patch.object(settings(), "github_app_client_id", "a-client-id")
    resp = yield http_client.fetch(
        fe_url,
        method="GET",
        headers={"X-Grouper-User": user.username},
        follow_redirects=False,
        raise_error=False,
    )
    assert resp.code == 302
    redir_url = urlparse(resp.headers["Location"])
    assert redir_url.netloc == "github.com"
    assert redir_url.path == "/login/oauth/authorize"
    query_params = parse_qs(redir_url.query)
    assert query_params["client_id"] == ["a-client-id"]
    (state,) = query_params["state"]
    assert "github-link-state={}".format(state) in resp.headers["Set-cookie"]
    assert query_params["redirect_uri"] == [
        "http://127.0.0.1:8888/github/link_complete/{}".format(user.id)
    ]

    fe_url = url(
        base_url, "/github/link_complete/{}?code=tempcode&state={}".format(user.id, state)
    )
    with pytest.raises(HTTPError) as excinfo:
        yield http_client.fetch(
            fe_url,
            method="GET",
            headers={"X-Grouper-User": user.username, "Cookie": "github-link-state=bogus-state"},
        )
    assert excinfo.value.code == 400

    recorder = FakeGitHubHttpClient()
    proxy_plugin = PluginProxy([SecretPlugin()])
    mocker.patch("grouper.fe.handlers.github._get_github_http_client", lambda: recorder)
    mocker.patch("grouper.fe.handlers.github.get_plugin_proxy", lambda: proxy_plugin)
    mocker.patch.object(settings(), "http_proxy_host", "proxy-server")
    mocker.patch.object(settings(), "http_proxy_port", 42)
    resp = yield http_client.fetch(
        fe_url,
        method="GET",
        headers={"X-Grouper-User": user.username, "Cookie": "github-link-state=" + state},
    )
    authorize_request, user_request = recorder.requests
    assert authorize_request.proxy_host == "proxy-server"
    assert authorize_request.proxy_port == 42
    assert user_request.proxy_host == "proxy-server"
    assert user_request.proxy_port == 42
    authorize_params = parse_qs(authorize_request.body)
    assert authorize_params[b"code"] == [b"tempcode"]
    assert authorize_params[b"state"] == [state.encode("ascii")]
    assert authorize_params[b"client_id"] == [b"a-client-id"]
    assert authorize_params[b"client_secret"] == [b"client-secret"]
    assert user_request.headers["Authorization"] == "token a-access-token"
    assert (
        get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY) is not None
    )
    assert (
        get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY).data_value
        == "zorkian-on-gh"
    )

    audit_entries = AuditLog.get_entries(
        session, on_user_id=user.id, action="changed_github_username"
    )
    assert len(audit_entries) == 1
    assert audit_entries[0].description == "Changed GitHub username: zorkian-on-gh"

    fe_url = url(base_url, "/users/{}/github/clear".format(user.username))
    resp = yield http_client.fetch(
        fe_url, method="POST", headers={"X-Grouper-User": user.username}, body=b""
    )
    assert resp.code == 200
    assert get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY) is None

    audit_entries = AuditLog.get_entries(
        session, on_user_id=user.id, action="changed_github_username"
    )
    assert len(audit_entries) == 2
    audit_entries.sort(key=operator.attrgetter("id"))
    assert audit_entries[1].description == "Cleared GitHub link"


@pytest.mark.gen_test
def test_github_user_admin(session, users, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]
    set_user_metadata(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY, "zorkian")
    data = get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY)
    assert data
    assert data.data_value == "zorkian"

    # Another random user should not be able to clear the GitHub identity.
    fe_url = url(base_url, f"/users/{user.username}/github/clear")
    with pytest.raises(HTTPError) as excinfo:
        resp = yield http_client.fetch(
            fe_url, method="POST", headers={"X-Grouper-User": "oliver@a.co"}, body=b""
        )
    assert excinfo.value.code == 403
    data = get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY)
    assert data
    assert data.data_value == "zorkian"

    # A user admin should be able to clear the GitHub identity.
    resp = yield http_client.fetch(
        fe_url, method="POST", headers={"X-Grouper-User": "cbguder@a.co"}, body=b""
    )
    assert resp.code == 200
    assert get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY) is None
