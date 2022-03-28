from urllib.parse import urlencode

import pytest
from tornado.httpclient import HTTPError

from grouper.constants import USER_ADMIN, USER_ENABLE
from grouper.models.user import User
from grouper.models.user_token import UserToken
from grouper.permissions import get_or_create_permission
from grouper.plugin import set_global_plugin_proxy
from grouper.plugin.base import BasePlugin
from grouper.plugin.proxy import PluginProxy
from grouper.user_metadata import get_user_metadata, set_user_metadata
from grouper.user_token import add_new_user_token, disable_user_token
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
from tests.setup import SetupTest
from tests.url_util import url
from tests.util import get_groups, grant_permission


def test_basic_metadata(standard_graph, session, users, groups, permissions):  # noqa: F811
    """Test basic metadata functionality."""

    user_id = users["zorkian@a.co"].id

    assert len(get_user_metadata(session, users["zorkian@a.co"].id)) == 0, "No metadata yet"

    # Test setting "foo" to 1 works, and we get "1" back (metadata is defined as strings)
    set_user_metadata(session, user_id, "foo", 1)
    md = get_user_metadata(session, user_id)
    assert len(md) == 1, "One metadata item"
    assert [d.data_value for d in md if d.data_key == "foo"] == ["1"], "foo is 1"

    set_user_metadata(session, user_id, "bar", "test string")
    md = get_user_metadata(session, user_id)
    assert len(md) == 2, "Two metadata items"
    assert [d.data_value for d in md if d.data_key == "bar"] == [
        "test string"
    ], "bar is test string"

    set_user_metadata(session, user_id, "foo", "test2")
    md = get_user_metadata(session, user_id)
    assert len(md) == 2, "Two metadata items"
    assert [d.data_value for d in md if d.data_key == "foo"] == ["test2"], "foo is test2"

    set_user_metadata(session, user_id, "foo", None)
    md = get_user_metadata(session, user_id)
    assert len(md) == 1, "One metadata item"
    assert [d.data_value for d in md if d.data_key == "foo"] == [], "foo is not found"

    set_user_metadata(session, user_id, "baz", None)
    md = get_user_metadata(session, user_id)
    assert len(md) == 1, "One metadata item"


def test_usertokens(standard_graph, session, users, groups, permissions):  # noqa: F811
    user = users["zorkian@a.co"]
    assert len(user.tokens) == 0
    tok, secret = add_new_user_token(session, UserToken(user=user, name="Foo"))
    assert len(user.tokens) == 1

    assert tok.check_secret(secret)
    assert tok.check_secret("invalid") == False

    assert tok.enabled == True
    disable_user_token(session, tok)
    assert tok.enabled == False
    assert user.tokens[0].enabled == False
    assert UserToken.get(session, name="Foo", user=user).enabled == False
    assert tok.check_secret(secret) == False


@pytest.fixture
def user_admin_perm_to_auditors(session, groups):  # noqa: F811
    """Adds a USER_ADMIN permission to the "auditors" group"""
    user_admin_perm, is_new = get_or_create_permission(
        session, USER_ADMIN, description="grouper.admin.users permission"
    )
    session.commit()

    grant_permission(groups["auditors"], user_admin_perm)


@pytest.fixture
def user_enable_perm_to_sre(session, groups):  # noqa: F811
    """Adds the (USER_ENABLE, *) permission to the group `team-sre`"""
    user_enable_perm, is_new = get_or_create_permission(
        session, USER_ENABLE, description="grouper.user.enable perm"
    )
    session.commit()

    grant_permission(groups["team-sre"], user_enable_perm, argument="*")


@pytest.mark.gen_test
def test_user_tok_acls(
    session, graph, users, user_admin_perm_to_auditors, http_client, base_url  # noqa: F811
):
    role_user = "role@a.co"
    admin = "zorkian@a.co"
    pleb = "gary@a.co"

    # admin creating token for role user
    fe_url = url(base_url, "/users/{}/tokens/add".format(role_user))
    resp = yield http_client.fetch(
        fe_url, method="POST", headers={"X-Grouper-User": admin}, body=urlencode({"name": "foo"})
    )
    assert resp.code == 200

    with pytest.raises(HTTPError):
        # non-admin creating token for role user
        resp = yield http_client.fetch(
            fe_url,
            method="POST",
            headers={"X-Grouper-User": pleb},
            body=urlencode({"name": "foo2"}),
        )

    fe_url = url(base_url, "/users/{}/tokens/add".format(pleb))
    with pytest.raises(HTTPError):
        # admin creating token for normal (non-role) user
        resp = yield http_client.fetch(
            fe_url,
            method="POST",
            headers={"X-Grouper-User": admin},
            body=urlencode({"name": "foo3"}),
        )


@pytest.mark.gen_test
def test_graph_disable(
    session, graph, users, groups, user_admin_perm_to_auditors, http_client, base_url  # noqa: F811
):
    graph.update_from_db(session)
    old_users = graph.users
    assert sorted(old_users) == sorted(list(users.keys()) + ["service@a.co"])

    # disable a user
    username = "oliver@a.co"
    fe_url = url(base_url, "/users/{}/disable".format(username))
    resp = yield http_client.fetch(
        fe_url, method="POST", headers={"X-Grouper-User": "zorkian@a.co"}, body=urlencode({})
    )
    assert resp.code == 200

    graph.update_from_db(session)
    assert len(graph.users) == (len(old_users) - 1), "disabled user removed from graph"
    assert username not in graph.users


@pytest.mark.gen_test
def test_user_enable_disable(
    session,  # noqa: F811
    graph,  # noqa: F811
    users,  # noqa: F811
    user_admin_perm_to_auditors,
    user_enable_perm_to_sre,
    http_client,
    base_url,
):
    username = "oliver@a.co"
    old_groups = sorted(get_groups(graph, username))
    headers_admin = {"X-Grouper-User": "zorkian@a.co"}
    headers_enable = {"X-Grouper-User": "zay@a.co"}
    body_preserve = urlencode({"preserve_membership": "true"})
    body_base = urlencode({})

    # disable user
    fe_url = url(base_url, "/users/{}/disable".format(username))
    resp = yield http_client.fetch(fe_url, method="POST", headers=headers_admin, body=body_base)
    assert resp.code == 200

    # Attempt to enable user, preserving groups, as user with `grouper.user.enable`.
    # Should fail due to lack of admin perm.
    fe_url = url(base_url, "/users/{}/enable".format(username))
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(
            fe_url, method="POST", headers=headers_enable, body=body_preserve
        )

    # enable user, PRESERVE groups, as a user with the correct admin permission
    fe_url = url(base_url, "/users/{}/enable".format(username))
    resp = yield http_client.fetch(
        fe_url, method="POST", headers=headers_admin, body=body_preserve
    )
    assert resp.code == 200
    graph.update_from_db(session)
    assert old_groups == sorted(get_groups(graph, username)), "nothing should be removed"

    # disable user again
    fe_url = url(base_url, "/users/{}/disable".format(username))
    resp = yield http_client.fetch(fe_url, method="POST", headers=headers_admin, body=body_base)
    assert resp.code == 200

    # Attempt to enable user, PURGE groups. Should now succeed even with
    # only the `grouper.user.enable` perm.
    fe_url = url(base_url, "/users/{}/enable".format(username))
    resp = yield http_client.fetch(fe_url, method="POST", headers=headers_enable, body=body_base)
    assert resp.code == 200

    graph.update_from_db(session)
    assert len(get_groups(graph, username)) == 0, "all group membership should be removed"


class UserCreatedPlugin(BasePlugin):
    """Test plugin for checking user_created calls."""

    def __init__(self):
        # type: () -> None
        self.calls = 0
        self.expected_service_account = False

    def user_created(self, user, is_service_account=False):
        # type: (User, bool) -> None
        assert is_service_account == self.expected_service_account
        self.calls += 1


def test_user_created_plugin(setup: SetupTest):
    """Test calls to the user_created plugin."""
    plugin = UserCreatedPlugin()
    # WARN: Relies on the user_created function being called from the global proxy.
    # Will need to change once everything uses an injected plugin proxy.
    set_global_plugin_proxy(PluginProxy([plugin]))
    with setup.transaction():
        setup.create_user("human@a.co")
        assert plugin.calls == 1

        plugin.expected_service_account = True
        setup.create_service_account("service@a.co", "owner", "machine set", "desc")
        assert plugin.calls == 2
