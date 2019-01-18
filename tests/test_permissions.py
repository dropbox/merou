from collections import namedtuple
import unittest
from urllib import urlencode

import pytest
from tornado.httpclient import HTTPError
from wtforms.validators import ValidationError

from fixtures import standard_graph, graph, users, groups, service_accounts, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from grouper.constants import (
        ARGUMENT_VALIDATION,
        AUDIT_MANAGER,
        AUDIT_VIEWER,
        PERMISSION_ADMIN,
        PERMISSION_AUDITOR,
        PERMISSION_GRANT,
        PERMISSION_VALIDATION,
        SYSTEM_PERMISSIONS,
        )
from grouper.fe.forms import ValidateRegex
import grouper.fe.util
from grouper.models.async_notification import AsyncNotification
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount
from grouper.models.permission_map import PermissionMap
from grouper.models.user import User
from grouper.permissions import (
        CannotDisableASystemPermission,
        create_permission,
        disable_permission,
        filter_grantable_permissions,
        get_all_permissions,
        get_grantable_permissions,
        get_groups_by_permission,
        get_or_create_permission,
        get_owner_arg_list,
        get_owners_by_grantable_permission,
        get_permission,
        get_requests,
        grant_permission_to_service_account,
        )
from grouper.user_permissions import (
    user_grantable_permissions,
    user_has_permission,
    user_permissions,
)
from url_util import url
from util import get_group_permissions, get_user_permissions, grant_permission


@pytest.fixture
def grantable_permissions(session, standard_graph):
    perm_grant = create_permission(session, PERMISSION_GRANT)
    perm0 = create_permission(session, "grantable")
    perm1 = create_permission(session, "grantable.one")
    perm2 = create_permission(session, "grantable.two")
    session.commit()

    return perm_grant, perm0, perm1, perm2


def _get_unsent_and_mark_as_sent_emails(session):
    """Helper to count unsent emails and then mark them as sent."""
    emails = session.query(AsyncNotification).filter(AsyncNotification.sent == False).all()

    for email in emails:
        email.sent = True

    session.commit()
    return emails


def test_basic_permission(standard_graph, session, users, groups, permissions):  # noqa
    """ Test adding some permissions to various groups and ensuring that the permissions are all
        implemented as expected. This also tests permissions inheritance in the graph. """

    graph = standard_graph  # noqa

    assert sorted(get_group_permissions(graph, "team-sre")) == ["audited:", "ssh:*", "sudo:shell", "team-sre:*"]
    assert sorted(get_group_permissions(graph, "tech-ops")) == [
        "audited:", "ssh:shell", "sudo:shell"]
    assert sorted(get_group_permissions(graph, "team-infra")) == ["sudo:shell"]
    assert sorted(get_group_permissions(graph, "all-teams")) == []

    assert sorted(get_user_permissions(graph, "gary@a.co")) == [
        "audited:", "ssh:*", "ssh:shell", "sudo:shell", "team-sre:*"]
    assert sorted(get_user_permissions(graph, "zay@a.co")) == [
        "audited:", "ssh:*", "ssh:shell", "sudo:shell", "team-sre:*"]
    assert sorted(get_user_permissions(graph, "zorkian@a.co")) == [
        "audited:", AUDIT_MANAGER + ":", AUDIT_VIEWER + ":", PERMISSION_AUDITOR + ":",
        "owner:sad-team", "ssh:*", "sudo:shell", "team-sre:*"]
    assert sorted(get_user_permissions(graph, "testuser@a.co")) == []
    assert sorted(get_user_permissions(graph, "figurehead@a.co")) == [
        "sudo:shell"]


def test_has_permission(session, standard_graph, users):  # noqa
    """ Tests the has_permission method of a user object. """

    # In our setup, zorkian has 'audited' with no arguments
    assert user_has_permission(session, users["zorkian@a.co"], "audited"), "zorkian has permission audited"
    assert not user_has_permission(session, users["zorkian@a.co"], "audited", argument='foo'), \
        "zorkian has permission audited:foo"
    assert not user_has_permission(session, users["zorkian@a.co"], "audited", argument='*'), \
        "zorkian has permission audited:*"

    # zay has ssh:*
    assert user_has_permission(session, users["zay@a.co"], "ssh"), "zay has permission ssh"
    assert user_has_permission(session, users["zay@a.co"], "ssh", argument='foo'), "zay has permission ssh:foo"
    assert user_has_permission(session, users["zay@a.co"], "ssh", argument='*'), "zay has permission ssh:*"


class PermissionTests(unittest.TestCase):
    def test_reject_bad_permission_names(self):
        self.assertEquals(len(grouper.fe.util.test_reserved_names("permission_lacks_period")), 1)
        self.assertEquals(len(grouper.fe.util.test_reserved_names("grouper.prefix.reserved")), 1)
        self.assertEquals(len(grouper.fe.util.test_reserved_names("admin.prefix.reserved")), 1)
        self.assertEquals(len(grouper.fe.util.test_reserved_names("test.prefix.reserved")), 1)

        Field = namedtuple("field", "data")

        def eval_permission(perm):
            ValidateRegex(PERMISSION_VALIDATION)(form=None, field=Field(data=perm))

        self.assertIsNone(eval_permission('foo.bar'))
        self.assertIsNone(eval_permission('foobar'))
        self.assertIsNone(eval_permission('foo.bar_baz'))
        self.assertRaises(ValidationError, eval_permission, 'foo__bar')
        self.assertRaises(ValidationError, eval_permission, 'foo.bar.')
        self.assertRaises(ValidationError, eval_permission, 'foo._bar')

        def eval_argument(arg):
            ValidateRegex(ARGUMENT_VALIDATION)(form=None, field=Field(data=arg))

        self.assertIsNone(eval_argument('foo.bar'))
        self.assertIsNone(eval_argument('foobar'))
        self.assertIsNone(eval_argument('underscore_'))
        self.assertIsNone(eval_argument('equals='))
        self.assertIsNone(eval_argument('plus+'))
        self.assertIsNone(eval_argument('slash/'))
        self.assertIsNone(eval_argument('dot.'))
        self.assertIsNone(eval_argument('colon:'))
        self.assertIsNone(eval_argument('hyphen-'))
        self.assertIsNone(eval_argument('dollar_sign$'))
        self.assertIsNone(eval_argument('dollar$sign'))
        self.assertIsNone(eval_argument('left_bracket['))
        self.assertIsNone(eval_argument('right_bracket]'))
        self.assertIsNone(eval_argument('caret^'))
        self.assertIsNone(eval_argument('underscore_equals=plus+slash/dot.color:hyphen-ok'))
        self.assertIsNone(eval_argument('whitespace allowed'))
        self.assertRaises(ValidationError, eval_argument, 'question?mark')
        self.assertRaises(ValidationError, eval_argument, 'exclaimation!point')


def assert_same_recipients(emails, recipients, msg="email recipients did not match expectation"):
    actual_recipients = sorted(map(lambda email: email.email, emails))
    expected_recipients = sorted(recipients)
    assert actual_recipients == expected_recipients, msg


def test_grant_permission(session, standard_graph, groups, permissions):
    grant_permission(groups["sad-team"], permissions["ssh"], argument="host +other-host")
    with pytest.raises(AssertionError):
        grant_permission(groups["sad-team"], permissions["ssh"], argument="question?")
    account = ServiceAccount.get(session, name="service@a.co")
    grant_permission_to_service_account(session, account, permissions["ssh"], argument="*")
    with pytest.raises(AssertionError):
        grant_permission_to_service_account(
            session, account, permissions["ssh"], argument="question?")


def test_grantable_permissions(session, standard_graph, users, groups, grantable_permissions):
    perm_grant, perm0, perm1, _ = grantable_permissions

    assert not user_grantable_permissions(session, users["zorkian@a.co"]), "start with none"

    grant_permission(groups["auditors"], perm_grant, argument="notgrantable.one")
    assert not user_grantable_permissions(session, users["zorkian@a.co"]), "grant on non-existent is fine"

    grant_permission(groups["auditors"], perm_grant, argument=perm0.name)
    grants = user_grantable_permissions(session, users["zorkian@a.co"])
    assert len(grants) == 1, "only specific permission grant"
    assert grants[0][0].name == perm0.name, "only specific permission grant"

    grant_permission(groups["auditors"], perm_grant, argument="grantable.*")
    grants = user_grantable_permissions(session, users["zorkian@a.co"])
    assert len(grants) == 3, "wildcard grant should grab appropriat amount"
    assert sorted([x[0].name for x in grants]) == ["grantable", "grantable.one", "grantable.two"]

    args_by_perm = get_grantable_permissions(session, None)
    assert args_by_perm[perm1.name] == ["*"], "wildcard grant reflected in list of grantable"

    grant_permission(groups["auditors"], perm_grant, argument="{}/single_arg".format(perm1.name))
    args_by_perm = get_grantable_permissions(session, None)
    assert args_by_perm[perm1.name] == ["*"], "wildcard grant reflected cause no restricted perms"

    args_by_perm = get_grantable_permissions(session, [perm1.name])
    assert args_by_perm[perm1.name] == ["single_arg"], \
            "least permissive argument shown cause of restricted perms"


def test_permission_grant_to_owners(session, standard_graph, groups, grantable_permissions):
    """Test we're getting correct owners according to granted
    'grouper.permission.grant' permissions."""
    perm_grant, _, perm1, perm2 = grantable_permissions

    assert not get_owners_by_grantable_permission(session), 'nothing to begin with'

    # grant a grant on a non-existent permission
    grant_permission(groups["auditors"], perm_grant, argument="notgrantable.one")
    assert not get_owners_by_grantable_permission(session), 'ignore grants for non-existent perms'

    # grant a wildcard grant -- make sure all permissions are represented and
    # the grant isn't inherited
    grant_permission(groups["all-teams"], perm_grant, argument="grantable.*")
    owners_by_arg_by_perm = get_owners_by_grantable_permission(session)
    expected = [groups['all-teams']]
    assert owners_by_arg_by_perm[perm1.name]['*'] == expected, 'grants are not inherited'
    assert len(owners_by_arg_by_perm) == 2
    assert len(owners_by_arg_by_perm[perm1.name]) == 1
    assert len(owners_by_arg_by_perm[perm2.name]) == 1

    # grant on argument substring
    grant_permission(groups["team-sre"], perm_grant, argument="{}/somesubstring*".format(
            perm1.name))
    owners_by_arg_by_perm = get_owners_by_grantable_permission(session)
    expected = [groups['all-teams']]
    assert owners_by_arg_by_perm[perm1.name]['*'] == expected
    expected = [groups["team-sre"]]
    assert owners_by_arg_by_perm[perm1.name]['somesubstring*'] == expected

    # make sure get_owner() respect substrings
    res = [o for o, a in get_owner_arg_list(session, perm1, "somesubstring",
            owners_by_arg_by_perm=owners_by_arg_by_perm)]
    assert sorted(res) == sorted([groups["all-teams"], groups["team-sre"]]), \
            "should include substring wildcard matches"

    res = [o for o, a in get_owner_arg_list(session, perm1, "othersubstring",
            owners_by_arg_by_perm=owners_by_arg_by_perm)]
    assert sorted(res) == [groups["all-teams"]], "negative test of substring wildcard matches"

    # permission admins have all the power
    perm_admin = create_permission(session, PERMISSION_ADMIN)
    session.commit()
    grant_permission(groups["security-team"], perm_admin)

    owners_by_arg_by_perm = get_owners_by_grantable_permission(session)
    all_permissions = get_all_permissions(session)
    for perm in all_permissions:
        assert perm.name in owners_by_arg_by_perm, 'all permission should be represented'
        assert groups["security-team"] in owners_by_arg_by_perm[perm.name]["*"], \
                'permission admin should be wildcard owners'


def _load_permissions_by_group_name(session, group_name):
    group = Group.get(session, name=group_name)
    return [name for _, name, _, _, _ in group.my_permissions()]


@pytest.mark.gen_test
def test_permission_request_flow(session, standard_graph, groups, grantable_permissions,
        http_client, base_url):
    """Test that a permission request gets into the system correctly and
    notifications are sent correctly."""
    perm_grant, _, perm1, perm2 = grantable_permissions
    grant_permission(groups["all-teams"], perm_grant, argument="grantable.*")
    grant_permission(groups["security-team"], perm_grant, argument="grantable.one")
    grant_permission(groups["tech-ops"], perm_grant, argument="grantable.two")

    # REQUEST: permission with an invalid argument
    groupname = "serving-team"
    username = "zorkian@a.co"
    fe_url = url(base_url, "/groups/{}/permission/request".format(groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"permission_name": "grantable.one", "argument": "some argument?",
                "reason": "blah blah black sheep", "argument_type": "text"}),
            headers={'X-Grouper-User': username})
    assert resp.code == 200
    assert "Field must match" in resp.body
    emails = _get_unsent_and_mark_as_sent_emails(session)
    assert len(emails) == 0, "no emails queued"

    # REQUEST: 'grantable.one', 'some argument' for 'serving-team'
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"permission_name": "grantable.one", "argument": "some argument",
                "reason": "blah blah black sheep", "argument_type": "text"}),
            headers={'X-Grouper-User': username})
    assert resp.code == 200

    emails = _get_unsent_and_mark_as_sent_emails(session)
    assert_same_recipients(emails, [u"testuser@a.co", u"security-team@a.co"])

    perms = _load_permissions_by_group_name(session, 'serving-team')
    assert len(perms) == 1
    assert "grantable.one" not in perms, "requested permission shouldn't be granted immediately"

    user = User.get(session, name='zorkian@a.co')
    request_tuple, total = get_requests(session, "pending", 10, 0, owner=user)
    assert len(request_tuple.requests) == 0, "random user shouldn't have a request"

    user = User.get(session, name='testuser@a.co')
    request_tuple, total = get_requests(session, "pending", 10, 0, owner=user)
    assert len(request_tuple.requests) == 1, "user in group with grant should have a request"

    # APPROVE grant: have 'testuser@a.co' action this request as owner of
    # 'all-teams' which has the grant permission for the requested permission
    request_id = request_tuple.requests[0].id
    fe_url = url(base_url, "/permissions/requests/{}".format(request_id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"status": "actioned", "reason": "lgtm"}),
            headers={'X-Grouper-User': user.name})
    assert resp.code == 200

    perms = _load_permissions_by_group_name(session, 'serving-team')
    assert len(perms) == 2
    assert "grantable.one" in perms, "requested permission shouldn't be granted immediately"

    emails = _get_unsent_and_mark_as_sent_emails(session)
    assert_same_recipients(emails, [u"zorkian@a.co"])

    # (re)REQUEST: 'grantable.one', 'some argument' for 'serving-team'
    groupname = "serving-team"
    username = "zorkian@a.co"
    fe_url = url(base_url, "/groups/{}/permission/request".format(groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"permission_name": "grantable.one", "argument": "some argument",
                "reason": "blah blah black sheep", "argument_type": "text"}),
            headers={'X-Grouper-User': username})
    assert resp.code == 200

    user = User.get(session, name='testuser@a.co')
    request_tuple, total = get_requests(session, "pending", 10, 0, owner=user)
    assert len(request_tuple.requests) == 0, "request for existing perm should fail"

    # REQUEST: 'grantable.two', 'some argument' for 'serving-team'
    groupname = "serving-team"
    username = "zorkian@a.co"
    fe_url = url(base_url, "/groups/{}/permission/request".format(groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"permission_name": "grantable.two", "argument": "some argument",
                "reason": "blah blah black sheep", "argument_type": "text"}),
            headers={'X-Grouper-User': username})
    assert resp.code == 200

    emails = _get_unsent_and_mark_as_sent_emails(session)
    # because tech-ops team doesn't have an email, all of its members should get emailed instead
    assert_same_recipients(emails, [u"testuser@a.co", u"zay@a.co", u"gary@a.co", u"figurehead@a.co"])

    perms = _load_permissions_by_group_name(session, 'serving-team')
    assert len(perms) == 2
    assert "grantable.two" not in perms, "requested permission shouldn't be granted immediately"

    user = User.get(session, name='zorkian@a.co')
    request_tuple, total = get_requests(session, "pending", 10, 0, owner=user)
    assert len(request_tuple.requests) == 0, "random user shouldn't have a request"

    user = User.get(session, name='testuser@a.co')
    request_tuple, total = get_requests(session, "pending", 10, 0, owner=user)
    assert len(request_tuple.requests) == 1, "user in group with grant should have a request"

    # CANCEL request: have 'testuser@a.co' cancel this request
    request_id = request_tuple.requests[0].id
    fe_url = url(base_url, "/permissions/requests/{}".format(request_id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"status": "cancelled", "reason": "heck no"}),
            headers={'X-Grouper-User': user.name})
    assert resp.code == 200

    emails = _get_unsent_and_mark_as_sent_emails(session)
    assert_same_recipients(emails, [u"zorkian@a.co"])

    perms = _load_permissions_by_group_name(session, 'serving-team')
    assert len(perms) == 2
    assert "grantable.two" not in perms, "no new permissions should be granted for this"

@pytest.mark.gen_test
def test_limited_permissions(session, standard_graph, groups, grantable_permissions,
        http_client, base_url):
    """Test that notifications are not sent to wildcard grant owners unless necessary."""
    perm_grant, _, perm1, _ = grantable_permissions
    # one super wildcard, one wildcard grant and one specific grant
    grant_permission(groups["sad-team"], perm_grant, argument="*")
    grant_permission(groups["all-teams"], perm_grant, argument="grantable.*")
    grant_permission(groups["security-team"], perm_grant,
            argument="{}/specific_arg".format(perm1.name))

    security_team_members = {name for (t, name) in groups['security-team'].my_members().keys()
            if t == 'User'}

    # SPECIFIC REQUEST: 'grantable.one', 'specific_arg' for 'sad-team'
    groupname = "sad-team"
    username = "zorkian@a.co"
    fe_url = url(base_url, "/groups/{}/permission/request".format(groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"permission_name": perm1.name, "argument": "specific_arg",
                "reason": "blah blah black sheep", "argument_type": "text"}),
            headers={'X-Grouper-User': username})
    assert resp.code == 200

    emails = _get_unsent_and_mark_as_sent_emails(session)
    assert_same_recipients(emails, [u"security-team@a.co"])

@pytest.mark.gen_test
def test_limited_permissions_global_approvers(session, standard_graph, groups, grantable_permissions,
        http_client, base_url):
    """Test that notifications are not sent to global approvers."""
    perm_grant, _, perm1, _ = grantable_permissions
    perm_admin = create_permission(session, PERMISSION_ADMIN)
    session.commit()
    # one circuit-breaking admin grant, one wildcard grant
    grant_permission(groups["sad-team"], perm_admin, argument="")
    grant_permission(groups["security-team"], perm_grant, argument="grantable.*")

    security_team_members = {name for (t, name) in groups['security-team'].my_members().keys()
            if t == 'User'}

    # SPECIFIC REQUEST: 'grantable.one', 'specific_arg' for 'sad-team'
    groupname = "sad-team"
    username = "zorkian@a.co"
    fe_url = url(base_url, "/groups/{}/permission/request".format(groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"permission_name": perm1.name, "argument": "specific_arg",
                "reason": "blah blah black sheep", "argument_type": "text"}),
            headers={'X-Grouper-User': username})
    assert resp.code == 200

    emails = _get_unsent_and_mark_as_sent_emails(session)
    assert_same_recipients(emails, [u"security-team@a.co"])

@pytest.mark.gen_test
def test_regress_permreq_global_approvers(session, standard_graph, groups, grantable_permissions,
        http_client, base_url):
    """Validates that we can render a permission request form where a global approver exists"""
    perm_grant, _, perm1, _ = grantable_permissions
    perm_admin = create_permission(session, PERMISSION_ADMIN)
    session.commit()
    grant_permission(groups["security-team"], perm_admin)

    groupname = "sad-team"
    username = "zorkian@a.co"
    fe_url = url(base_url, "/groups/{}/permission/request".format(groupname))
    resp = yield http_client.fetch(fe_url, method="GET",
            headers={'X-Grouper-User': username})
    assert resp.code == 200

@pytest.mark.gen_test
def test_grant_and_revoke(session, standard_graph, graph, groups, permissions,
        http_client, base_url):
    """Test that permission grant and revokes are reflected correctly."""
    group_name = "team-sre"
    permission_name = "sudo"
    user_name = "oliver@a.co"

    def _check_graph_for_perm(graph):
        return any(map(lambda x: x.permission == permission_name,
                graph.permission_metadata[group_name]))

    # make some permission admins
    perm_admin = create_permission(session, PERMISSION_ADMIN)
    session.commit()
    grant_permission(groups["security-team"], perm_admin)

    # grant attempt by non-permission admin
    fe_url = url(base_url, "/permissions/grant/{}".format(group_name))
    with pytest.raises(HTTPError):
        yield http_client.fetch(fe_url, method="POST",
                body=urlencode({"permission": permission_name, "argument": "specific_arg"}),
                headers={'X-Grouper-User': "zorkian@a.co"})

    graph.update_from_db(session)
    assert not _check_graph_for_perm(graph), "no permissions granted"

    # grant by permission admin
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"permission": permission_name, "argument": "specific_arg"}),
            headers={'X-Grouper-User': user_name})
    assert resp.code == 200

    graph.update_from_db(session)
    assert _check_graph_for_perm(graph), "permissions granted, successfully"

    # figure out mapping_id of grant
    permission_id = get_permission(session, permission_name).id
    group_id = Group.get(session, name=group_name).id
    mapping = session.query(PermissionMap).filter(
            PermissionMap.permission_id == permission_id,
            PermissionMap.group_id == group_id).first()

    # revoke permission by non-admin
    fe_url = url(base_url, "/permissions/{}/revoke/{}".format(permission_name, mapping.id))
    with pytest.raises(HTTPError):
        yield http_client.fetch(fe_url, method="POST", body=urlencode({}),
                headers={'X-Grouper-User': "zorkian@a.co"})

    graph.update_from_db(session)
    assert _check_graph_for_perm(graph), "permissions not revoked"

    # revoke permission for realz
    resp = yield http_client.fetch(fe_url, method="POST", body=urlencode({}),
            headers={'X-Grouper-User': user_name})
    assert resp.code == 200

    graph.update_from_db(session)
    assert not _check_graph_for_perm(graph), "permissions revoked successfully"


@pytest.mark.gen_test
def test_disabling_permission(session, groups, standard_graph, http_client, base_url):
    """
    This tests disabling via the front-end route, including checking
    that the user is authorized to disable permissions.
    """
    perm_name = 'sudo'
    nonpriv_user_name = 'oliver@a.co' # user without PERMISSION_ADMIN
    nonpriv_headers = {'X-Grouper-User': nonpriv_user_name}
    priv_user_name = 'cbguder@a.co' # user with PERMISSION_ADMIN
    priv_headers = {'X-Grouper-User': priv_user_name}
    disable_url = url(base_url, '/permissions/{}/disable'.format(perm_name))
    disable_url_non_exist_perm = url(base_url, '/permissions/no.exists/disable')

    graph = standard_graph

    perm_admin = create_permission(session, PERMISSION_ADMIN)
    session.commit()
    # overload `group-admins` for also permission admin
    grant_permission(groups["group-admins"], perm_admin)

    assert get_permission(session, perm_name).enabled
    assert 'sudo:shell' in get_user_permissions(graph, 'gary@a.co')
    assert 'sudo:shell' in get_user_permissions(graph, 'oliver@a.co')

    # attempt to disable the permission -> should fail cuz actor
    # doesn't have PERMISSION_ADMIN
    with pytest.raises(HTTPError) as exc:
        yield http_client.fetch(disable_url, method="POST", headers=nonpriv_headers, body="")
    assert exc.value.code == 403
    # check that no change
    assert get_permission(session, perm_name).enabled
    graph.update_from_db(session)
    assert 'sudo:shell' in get_user_permissions(graph, 'gary@a.co')
    assert 'sudo:shell' in get_user_permissions(graph, 'oliver@a.co')

    # an actor with PERMISSION_ADMIN is allowed to disable the
    # permission
    resp = yield http_client.fetch(disable_url, method="POST", headers=priv_headers, body="")
    assert resp.code == 200
    assert not get_permission(session, perm_name).enabled
    graph.update_from_db(session)
    assert not 'sudo:shell' in get_user_permissions(graph, 'gary@a.co')
    assert not 'sudo:shell' in get_user_permissions(graph, 'oliver@a.co')

    with pytest.raises(HTTPError) as exc:
        yield http_client.fetch(
            disable_url_non_exist_perm, method="POST", headers=priv_headers, body="")
    assert exc.value.code == 404

    #
    # make sure that when disabling the permission, all mappings of
    # it, i.e., with different arguments, are disabled
    #

    # the standard_graph grants 'ssh' with args '*' and 'shell' to two
    # different groups
    assert "ssh:*" in get_group_permissions(graph, "team-sre")
    assert "ssh:shell" in get_group_permissions(graph, "tech-ops")
    # disable the perm
    disable_url_ssh_pem = url(base_url, '/permissions/ssh/disable')
    resp = yield http_client.fetch(
        disable_url_ssh_pem, method="POST", headers=priv_headers, body="")
    assert resp.code == 200
    assert not get_permission(session, "ssh").enabled
    graph.update_from_db(session)
    assert not "ssh:*" in get_group_permissions(graph, "team-sre")
    assert not "ssh:shell" in get_group_permissions(graph, "tech-ops")

@pytest.mark.parametrize('perm_name', (entry[0] for entry in SYSTEM_PERMISSIONS))
def test_reject_disabling_system_permissions(perm_name, session, permissions):
    get_or_create_permission(session, perm_name)
    with pytest.raises(CannotDisableASystemPermission) as exc:
        disable_permission(session, perm_name, 0)
    assert exc.value.name == perm_name


def test_exclude_disabled_permissions(
        session, standard_graph, users, groups, permissions):
    """
    Ensure that disabled permissions are excluded from various
    functions/methods that return data from the models.
    """
    perm_ssh = get_permission(session, "ssh")
    perm_admin = create_permission(session, PERMISSION_ADMIN)
    perm_grant = create_permission(session, PERMISSION_GRANT)
    session.commit()
    # overload `group-admins` for also permission admin
    grant_permission(groups["group-admins"], perm_admin)
    # this user has grouper.permission.grant with argument "ssh/*"
    grant_permission(groups["group-admins"], perm_grant, argument="ssh/*")
    graph = standard_graph
    graph.update_from_db(session)

    grant_perms = [x for x in user_permissions(session, users['cbguder@a.co'])
                   if x.name == PERMISSION_GRANT]
    assert 'ssh' == filter_grantable_permissions(session, grant_perms)[0][0].name
    assert "ssh" in (p.name for p in get_all_permissions(session))
    assert "ssh" in (p.name for p in get_all_permissions(session, include_disabled=False))
    assert "ssh" in (p.name for p in get_all_permissions(session, include_disabled=True))
    assert "ssh" in get_grantable_permissions(session, [])
    assert "team-sre" in [g[0] for g in get_groups_by_permission(session, perm_ssh)]
    assert get_owner_arg_list(session, perm_ssh, "*")
    assert "ssh" in get_owners_by_grantable_permission(session)
    assert 'ssh' in (x[0].name for x in user_grantable_permissions(session, users['cbguder@a.co']))
    assert user_has_permission(session, users['zay@a.co'], 'ssh')
    assert 'ssh' in (p.name for p in user_permissions(session, users['zay@a.co']))
    assert 'ssh' in (p['permission'] for p in graph.get_group_details('team-sre')['permissions'])
    assert 'ssh' in (pt.name for pt in graph.get_permissions())
    assert 'team-sre' in graph.get_permission_details('ssh')['groups']
    assert 'ssh' in (p['permission'] for p in graph.get_user_details('zay@a.co')['permissions'])

    # now disable the ssh permission
    disable_permission(session, "ssh", users['cbguder@a.co'].id)
    graph.update_from_db(session)

    grant_perms = [x for x in user_permissions(session, users['cbguder@a.co'])
                   if x.name == PERMISSION_GRANT]
    assert not filter_grantable_permissions(session, grant_perms)
    assert not "ssh" in (p.name for p in get_all_permissions(session))
    assert not "ssh" in (p.name for p in get_all_permissions(session, include_disabled=False))
    assert "ssh" in (p.name for p in get_all_permissions(session, include_disabled=True))
    assert not "ssh" in get_grantable_permissions(session, [])
    assert not get_groups_by_permission(session, perm_ssh)
    assert not get_owner_arg_list(session, perm_ssh, "*")
    assert not "ssh" in get_owners_by_grantable_permission(session)
    assert not 'ssh' in (x[0].name for x in user_grantable_permissions(session, users['cbguder@a.co']))
    assert not user_has_permission(session, users['zay@a.co'], 'ssh')
    assert not 'ssh' in (p.name for p in user_permissions(session, users['zay@a.co']))
    assert not 'ssh' in (p['permission'] for p in graph.get_group_details('team-sre')['permissions'])
    assert not 'ssh' in (pt.name for pt in graph.get_permissions())
    assert not graph.get_permission_details('ssh')['groups']
    assert not 'ssh' in (p['permission'] for p in graph.get_user_details('zay@a.co')['permissions'])
