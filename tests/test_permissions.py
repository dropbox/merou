import pytest
import unittest

from collections import namedtuple
from mock import patch
from urllib import urlencode

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
        )
from grouper.fe.forms import ValidateRegex
import grouper.fe.util
from grouper.models.async_notification import AsyncNotification
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount
from grouper.models.permission_map import PermissionMap
from grouper.models.user import User
from grouper.permissions import (
        enable_permission_auditing,
        get_grantable_permissions,
        get_owner_arg_list,
        get_owners_by_grantable_permission,
        get_requests_by_owner,
        grant_permission_to_service_account,
        )
from grouper.models.permission import Permission
from grouper.user_permissions import user_grantable_permissions, user_has_permission
from url_util import url
from util import (
    add_member,
    get_group_permissions,
    get_user_permissions,
    grant_permission,
    get_users,
)


@pytest.fixture
def grantable_permissions(session, standard_graph):
    perm_grant, _ = Permission.get_or_create(session, name=PERMISSION_GRANT, description="")
    perm0, _ = Permission.get_or_create(session, name="grantable", description="")
    perm1, _ = Permission.get_or_create(session, name="grantable.one", description="")
    perm2, _ = Permission.get_or_create(session, name="grantable.two", description="")
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
    perm_admin, _ = Permission.get_or_create(session, name=PERMISSION_ADMIN, description="")
    session.commit()
    grant_permission(groups["security-team"], perm_admin)

    owners_by_arg_by_perm = get_owners_by_grantable_permission(session)
    all_permissions = Permission.get_all(session)
    for perm in all_permissions:
        assert perm.name in owners_by_arg_by_perm, 'all permission should be represented'
        assert groups["security-team"] in owners_by_arg_by_perm[perm.name]["*"], \
                'permission admin should be wildcard owners'


def test_auditor_promition_when_enabling_permission_auditing(
        session, graph, permissions):
    """Test automatic promotion of non-auditor approvers

    Two cases for this promotion: 1) when a permission becomes
    audited, it can cause groups to be come audited, and we promote
    non-auditor approvers of those groups; 2) when a non-auditor
    approver is added to an audited group.

    We use the standard_graph fixture here only for the `auditors`
    group that it sets up---though we may choose to not use it at all
    and just set up. Then we set up our own little graph in here for
    testing because it would be a little too annoying to modify the
    existing standard_graph fixture while not breaking existing tests.

    very-special-auditors:
      (initially empty)

    group-1:
      * user11 (o)
      * user12
      * user13 (np-o)
      * user14 (o, a)

    group-2:
      * user21 (o)
      * user22
      * service

    group-3:
      * user22 (o)
      * user12 (o)

    group-4:
      * user41
      * user42 (o)
      * user43 (np-o)

    o: owner, np-o: no-permission owner, a: auditor

    group-1 and group-2 have the permission that we will enable
    auditing. group-4 will also have it, inheriting from group-1.

    The expected outcome is: user11, user13, user21, user42, and
    user43 will be added to the auditors group.
    """

    #
    # set up our test part of the graph
    #

    # create groups
    AUDITORS_GROUP = "very-special-auditors"
    groups = {
        groupname: Group.get_or_create(session, groupname=groupname)[0]
        for groupname in ("group-1", "group-2", "group-3", "group-4", AUDITORS_GROUP)
    }
    # create users
    users = {
        username + '@a.co': User.get_or_create(session, username=username + '@a.co')[0]
        for username in ("user11", "user12", "user13", "user14",
                         "user21", "user22", "user23",
                         "user41", "user42", "user43",
        )
    }
    # create permissions
    permissions.update({
        permission: Permission.get_or_create(
            session, name=permission, description="{} permission".format(permission)
        )[0]
        for permission in ["test-permission"]
    })
    # add users to groups
    for (groupname, username, role) in (("group-1", "user11", "owner"),
                                        ("group-1", "user12", "member"),
                                        ("group-1", "user13", "np-owner"),
                                        ("group-1", "user14", "owner"),
                                        ("group-2", "user21", "owner"),
                                        ("group-2", "user22", "member"),
                                        ("group-3", "user12", "owner"),
                                        ("group-3", "user22", "owner"),
                                        ("group-4", "user41", "member"),
                                        ("group-4", "user42", "owner"),
                                        ("group-4", "user43", "np-owner"),
                                        ):
        add_member(groups[groupname], users[username + "@a.co"], role=role)
    # add group-4 as member of group-1
    add_member(groups["group-1"], groups["group-4"])
    # grant permissions to groups
    #
    # give the test permission to groups 1 and 2, and group 4 should
    # also inherit from group 1
    grant_permission(groups["group-1"], permissions["test-permission"])
    grant_permission(groups["group-2"], permissions["test-permission"])
    grant_permission(groups[AUDITORS_GROUP], permissions[PERMISSION_AUDITOR])

    session.commit()
    graph.update_from_db(session)
    # done setting up

    # now a few pre-op checks
    assert not graph.get_group_details('group-1').get('audited')
    assert not graph.get_group_details('group-4').get('audited')
    assert not get_users(graph, AUDITORS_GROUP)
    assert get_users(graph, "group-3") == set(["user12@a.co", "user22@a.co"])

    # DO IT!
    with patch('grouper.permissions.get_auditors_group_name', return_value=AUDITORS_GROUP):
        enable_permission_auditing(session, "test-permission",
                                   User.get(session, name="cbguder@a.co"))

    # check it!
    graph.update_from_db(session)
    assert graph.get_group_details('group-1').get('audited')
    assert graph.get_group_details('group-4').get('audited')
    assert get_users(graph, AUDITORS_GROUP) == set([
        "user14@a.co", "user11@a.co", "user13@a.co", "user21@a.co", "user42@a.co", "user43@a.co"])


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
    request_tuple, total = get_requests_by_owner(session, user, "pending", 10, 0)
    assert len(request_tuple.requests) == 0, "random user shouldn't have a request"

    user = User.get(session, name='testuser@a.co')
    request_tuple, total = get_requests_by_owner(session, user, "pending", 10, 0)
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
    request_tuple, total = get_requests_by_owner(session, user, "pending", 10, 0)
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
    request_tuple, total = get_requests_by_owner(session, user, "pending", 10, 0)
    assert len(request_tuple.requests) == 0, "random user shouldn't have a request"

    user = User.get(session, name='testuser@a.co')
    request_tuple, total = get_requests_by_owner(session, user, "pending", 10, 0)
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
    perm_admin, _ = Permission.get_or_create(session, name=PERMISSION_ADMIN, description="")
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
    perm_admin, _ = Permission.get_or_create(session, name=PERMISSION_ADMIN, description="")
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
    perm_admin, _ = Permission.get_or_create(session, name=PERMISSION_ADMIN, description="")
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
    permission_id = Permission.get(session, name=permission_name).id
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
