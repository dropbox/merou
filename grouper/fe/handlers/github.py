import binascii
import hmac
import json
import os
from typing import cast, TYPE_CHECKING

from six.moves.urllib.parse import urlencode
from tornado import gen, httpclient

from grouper.constants import USER_METADATA_GITHUB_USERNAME_KEY
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.plugin import get_plugin_proxy
from grouper.user_metadata import set_user_metadata

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from tornado.concurrent import Future
    from typing import Any, Iterator, Optional, Text


def _get_github_http_client():
    # type: () -> httpclient.AsyncHTTPClient
    return httpclient.AsyncHTTPClient()


class GitHubClient(object):
    def __init__(self, http_client, proxy_host, proxy_port):
        # type: (httpclient.AsyncHTTPClient, Optional[str], Optional[int]) -> None
        self.http_client = http_client
        self.proxy_host = proxy_host
        self.proxy_port = proxy_port

    @gen.coroutine
    def get_oauth_access_token(self, client_id, client_secret, code, state):
        # type: (bytes, Text, bytes, bytes) -> Iterator[Future]
        "Turn a temporary oauth code into an access token."
        request = httpclient.HTTPRequest(
            "https://github.com/login/oauth/access_token",
            "POST",
            {"Accept": "application/json", "User-Agent": "github.com/dropbox/merou"},
            body=urlencode(
                {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "state": state,
                }
            ),
            proxy_host=self.proxy_host,
            proxy_port=self.proxy_port,
        )
        response = cast(httpclient.HTTPResponse, (yield self.http_client.fetch(request)))
        response_data = json.loads(response.body.decode("utf-8"))
        if "error" in response_data:
            raise ValueError("GitHub returned an error: {!r}".format(response_data))
        raise gen.Return(response_data["access_token"])

    @gen.coroutine
    def get_username(self, oauth_token):
        # type: (Text) -> Iterator[Future]
        "Get the GitHub username associated with an oauth token."
        request = httpclient.HTTPRequest(
            "https://api.github.com/user",
            "GET",
            {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": "token " + oauth_token,
                "User-Agent": "github.com/dropbox/merou",
            },
            proxy_host=self.proxy_host,
            proxy_port=self.proxy_port,
        )
        response = cast(httpclient.HTTPResponse, (yield self.http_client.fetch(request)))
        response_data = json.loads(response.body.decode("utf-8"))
        raise gen.Return(response_data["login"])


class GitHubLinkBeginView(GrouperHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        # Redirect the user to GitHub to authorize our app.
        state = binascii.hexlify(os.urandom(16))
        self.set_cookie("github-link-state", state, httponly=True)
        params = {
            "client_id": settings().github_app_client_id,
            "state": state,
            "redirect_uri": "{}/github/link_complete/{}".format(settings().url, kwargs["user_id"]),
        }
        self.redirect("https://github.com/login/oauth/authorize?" + urlencode(params))


class GitHubLinkCompleteView(GrouperHandler):
    @gen.coroutine
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> Iterator[Future]
        # Check that the state parameter is correct.
        state = self.request.query_arguments.get("state", [b""])[-1]
        expected_state = self.get_cookie("github-link-state", "").encode("utf-8")
        self.clear_cookie("github-link-state")
        if not hmac.compare_digest(state, expected_state):
            self.badrequest()
            return

        code = self.get_query_argument("code")

        # Make sure we're modifying the authenticated user before doing more.
        user_id = kwargs["user_id"]
        user = User.get(self.session, user_id)
        if not user:
            self.notfound()
            return
        if self.current_user.id != user.id:
            self.forbidden()
            return

        github_client = GitHubClient(
            _get_github_http_client(), settings().http_proxy_host, settings().http_proxy_port
        )
        oauth_token = yield github_client.get_oauth_access_token(
            settings().github_app_client_id,
            get_plugin_proxy().get_github_app_client_secret(),
            code,
            state,
        )
        gh_username = yield github_client.get_username(oauth_token)

        AuditLog.log(
            self.session,
            self.current_user.id,
            "changed_github_username",
            "Changed GitHub username: {}".format(gh_username),
            on_user_id=user.id,
        )
        set_user_metadata(self.session, user.id, USER_METADATA_GITHUB_USERNAME_KEY, gh_username)

        self.redirect("/users/{}?refresh=yes".format(user.name))


class UserClearGitHub(GrouperHandler):
    @staticmethod
    def check_access(session, actor, target):
        # type: (Session, User, User) -> bool
        return actor.name == target.name

    def post(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        user_id = kwargs.get("user_id")  # type: Optional[int]
        name = kwargs.get("name")  # type: Optional[str]

        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        set_user_metadata(self.session, user.id, USER_METADATA_GITHUB_USERNAME_KEY, None)

        AuditLog.log(
            self.session,
            self.current_user.id,
            "changed_github_username",
            "Cleared GitHub link",
            on_user_id=user.id,
        )

        return self.redirect("/users/{}?refresh=yes".format(user.name))
