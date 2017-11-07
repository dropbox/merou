from urllib import urlencode

from mock import patch
import pytest

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from grouper.models.group import Group
from grouper.models.group_edge import GROUP_EDGE_ROLES
from grouper.role_user import create_role_user
from page import Page
from plugins.group_ownership_policy import GroupOwnershipPolicyPlugin
from url_util import url


@pytest.mark.gen_test
def test_list_groups(session, groups, users, http_client, base_url):
    headers = {"X-Grouper-User": "gary@a.co"}

    fe_url = url(base_url, "/groups")
    resp = yield http_client.fetch(fe_url, headers=headers)
    assert resp.code == 200

    page = Page(resp.body)

    for name, _ in groups.iteritems():
        path = "/groups/{}".format(name)
        assert page.has_link(name, path)


@pytest.mark.gen_test
def test_show_group(session, groups, users, http_client, base_url):
    headers = {"X-Grouper-User": "gary@a.co"}

    group = groups["team-sre"]
    members = group.my_members()

    fe_url = url(base_url, "/groups/{}".format(group.groupname))
    resp = yield http_client.fetch(fe_url, headers=headers)
    assert resp.code == 200

    page = Page(resp.body)

    for k, _ in members.iteritems():
        assert page.has_text(k[1])


@pytest.mark.gen_test
def test_remove_member(session, http_client, base_url):
    headers = {"X-Grouper-User": "gary@a.co"}

    members = Group.get(session, name="team-sre").my_users()
    assert ("zorkian@a.co", GROUP_EDGE_ROLES.index("member")) in members

    fe_url = url(base_url, "/groups/team-sre/remove")
    body = {"member_type": "user", "member": "zorkian@a.co"}
    resp = yield http_client.fetch(fe_url, method="POST", headers=headers, body=urlencode(body))
    assert resp.code == 200

    members = Group.get(session, name="team-sre").my_users()
    assert ("zorkian@a.co", GROUP_EDGE_ROLES.index("member")) not in members


@pytest.mark.gen_test
def test_remove_last_owner(session, http_client, base_url):
    headers = {"X-Grouper-User": "cbguder@a.co"}

    members = Group.get(session, name="team-sre").my_users()
    assert ("gary@a.co", GROUP_EDGE_ROLES.index("owner")) in members

    fe_url = url(base_url, "/groups/team-sre/remove")
    body = {"member_type": "user", "member": "gary@a.co"}

    with patch("grouper.group_member.get_plugins") as get_plugins:
        get_plugins.return_value = [GroupOwnershipPolicyPlugin()]
        resp = yield http_client.fetch(fe_url, method="POST", headers=headers, body=urlencode(body))

    assert resp.code == 200

    page = Page(resp.body)
    assert page.has_text("You can't remove the last permanent owner of a group")
    assert page.has_element("h2", "Groups")

    members = Group.get(session, name="team-sre").my_users()
    assert ("gary@a.co", GROUP_EDGE_ROLES.index("owner")) in members


@pytest.mark.gen_test
def test_expire_last_owner(session, http_client, base_url):
    headers = {"X-Grouper-User": "cbguder@a.co"}

    fe_url = url(base_url, "/groups/sad-team/edit/user/zorkian@a.co")
    body = {"role": "owner", "reason": "because", "expiration": "12/31/2999"}

    with patch("grouper.group_member.get_plugins") as get_plugins:
        get_plugins.return_value = [GroupOwnershipPolicyPlugin()]
        resp = yield http_client.fetch(fe_url, method="POST", headers=headers, body=urlencode(body))

    assert resp.code == 200

    page = Page(resp.body)
    assert page.has_text("You can't remove the last permanent owner of a group")
    assert page.has_element("h2", "Groups")

    members = Group.get(session, name="sad-team").my_users()
    assert ("zorkian@a.co", GROUP_EDGE_ROLES.index("owner")) in members


@pytest.mark.gen_test
def test_remove_last_owner_of_service_account(session, users, http_client, base_url):
    headers = {"X-Grouper-User": "cbguder@a.co"}

    create_role_user(session, users["gary@a.co"], "service@svc.localhost", "things", "canask")

    fe_url = url(base_url, "/groups/service@svc.localhost/remove")
    body = {"member_type": "user", "member": "gary@a.co"}

    with patch("grouper.group_member.get_plugins") as get_plugins:
        get_plugins.return_value = [GroupOwnershipPolicyPlugin()]
        resp = yield http_client.fetch(fe_url, method="POST", headers=headers, body=urlencode(body))

    assert resp.code == 200

    page = Page(resp.body)
    assert page.has_text("You can't remove the last permanent owner of a group")
    assert page.has_element("h2", "Service Accounts")

    members = Group.get(session, name="service@svc.localhost").my_users()
    assert ("gary@a.co", GROUP_EDGE_ROLES.index("np-owner")) in members
