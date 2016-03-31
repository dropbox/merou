from urllib import urlencode

import pytest

from fixtures import fe_app as app
from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from grouper.constants import USER_ADMIN
from grouper.model_soup import Permission
from grouper.models.user_token import UserToken
from grouper.user_token import add_new_user_token, disable_user_token
from url_util import url
from util import get_groups, grant_permission


def test_basic_metadata(standard_graph, session, users, groups, permissions):  # noqa
    """ Test basic metadata functionality. """

    graph = standard_graph  # noqa

    assert len(users["zorkian@a.co"].my_metadata()) == 0, "No metadata yet"

    # Test setting "foo" to 1 works, and we get "1" back (metadata is defined as strings)
    users["zorkian@a.co"].set_metadata("foo", 1)
    md = users["zorkian@a.co"].my_metadata()
    assert len(md) == 1, "One metadata item"
    assert [d.data_value for d in md if d.data_key == "foo"] == ["1"], "foo is 1"

    users["zorkian@a.co"].set_metadata("bar", "test string")
    md = users["zorkian@a.co"].my_metadata()
    assert len(md) == 2, "Two metadata items"
    assert [d.data_value for d in md if d.data_key == "bar"] == ["test string"], \
        "bar is test string"

    users["zorkian@a.co"].set_metadata("foo", "test2")
    md = users["zorkian@a.co"].my_metadata()
    assert len(md) == 2, "Two metadata items"
    assert [d.data_value for d in md if d.data_key == "foo"] == ["test2"], "foo is test2"

    users["zorkian@a.co"].set_metadata("foo", None)
    md = users["zorkian@a.co"].my_metadata()
    assert len(md) == 1, "One metadata item"
    assert [d.data_value for d in md if d.data_key == "foo"] == [], "foo is not found"

    users["zorkian@a.co"].set_metadata("baz", None)
    md = users["zorkian@a.co"].my_metadata()
    assert len(md) == 1, "One metadata item"


def test_usertokens(standard_graph, session, users, groups, permissions):  # noqa
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
def user_admin_perm_to_auditors(session, groups):
    """Adds a USER_ADMIN permission to the "auditors" group"""
    user_admin_perm, is_new = Permission.get_or_create(session, name=USER_ADMIN, description="")
    session.commit()

    grant_permission(groups["auditors"], user_admin_perm)


@pytest.mark.gen_test
def test_graph_disable(session, graph, users, groups, user_admin_perm_to_auditors,
        http_client, base_url):
    graph.update_from_db(session)
    old_users = graph.users
    assert sorted(old_users) == sorted(users.keys())

    # disable a user
    username = u"oliver@a.co"
    fe_url = url(base_url, "/users/{}/disable".format(username))
    resp = yield http_client.fetch(fe_url, method="POST",
            headers={"X-Grouper-User": "zorkian@a.co"}, body=urlencode({}))
    assert resp.code == 200

    graph.update_from_db(session)
    assert len(graph.users) == (len(old_users) - 1), 'disabled user removed from graph'
    assert username not in graph.users


@pytest.mark.gen_test
def test_user_disable(session, graph, users, user_admin_perm_to_auditors, http_client, base_url):
    username = u"oliver@a.co"
    old_groups = sorted(get_groups(graph, username))

    # disable user
    fe_url = url(base_url, "/users/{}/disable".format(username))
    resp = yield http_client.fetch(fe_url, method="POST",
            headers={"X-Grouper-User": "zorkian@a.co"}, body=urlencode({}))
    assert resp.code == 200

    # enable user, PRESERVE groups
    fe_url = url(base_url, "/users/{}/enable".format(username))
    resp = yield http_client.fetch(fe_url, method="POST",
            headers={"X-Grouper-User": "zorkian@a.co"},
            body=urlencode({"preserve_membership": "true"}))
    assert resp.code == 200
    graph.update_from_db(session)
    assert old_groups == sorted(get_groups(graph, username)), 'nothing should be removed'

    # disable and enable, PURGE groups
    fe_url = url(base_url, "/users/{}/disable".format(username))
    resp = yield http_client.fetch(fe_url, method="POST",
            headers={"X-Grouper-User": "zorkian@a.co"}, body=urlencode({}))
    assert resp.code == 200

    fe_url = url(base_url, "/users/{}/enable".format(username))
    resp = yield http_client.fetch(fe_url, method="POST",
            headers={"X-Grouper-User": "zorkian@a.co"}, body=urlencode({}))
    assert resp.code == 200

    graph.update_from_db(session)
    assert len(get_groups(graph, username)) == 0, 'all group membership should be removed'
