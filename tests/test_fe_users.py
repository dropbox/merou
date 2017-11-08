from urllib import urlencode

from mock import patch
import pytest

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from grouper.models.group import Group
from grouper.models.group_edge import GROUP_EDGE_ROLES
from page import Page
from plugins.group_ownership_policy import GroupOwnershipPolicyPlugin
from url_util import url


@pytest.mark.gen_test
def test_disable_last_owner(session, http_client, base_url):
    headers = {"X-Grouper-User": "tyleromeara@a.co"}

    members = Group.get(session, name="team-sre").my_users()
    assert ("gary@a.co", GROUP_EDGE_ROLES.index("owner")) in members

    fe_url = url(base_url, "/users/gary@a.co/disable")
    body = {"member_type": "user", "member": "gary@a.co"}

    with patch("grouper.user.get_plugins") as get_plugins:
        get_plugins.return_value = [GroupOwnershipPolicyPlugin()]
        resp = yield http_client.fetch(fe_url, method="POST", headers=headers, body=urlencode(body))

    assert resp.code == 200

    page = Page(resp.body)
    assert page.has_text("You can't remove the last permanent owner of a group")
    assert page.has_element("h2", "Users")

    members = Group.get(session, name="team-sre").my_users()
    assert ("gary@a.co", GROUP_EDGE_ROLES.index("owner")) in members
