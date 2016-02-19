from collections import namedtuple
from mock import patch
import re
import unittest
from urllib import urlencode

from wtforms.validators import ValidationError
import pytest

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from util import get_group_permissions, get_user_permissions, grant_permission
from grouper.constants import (
        ARGUMENT_VALIDATION,
        AUDIT_MANAGER,
        PERMISSION_AUDITOR,
        PERMISSION_GRANT,
        PERMISSION_VALIDATION,
        )
from grouper.fe.forms import ValidateRegex
import grouper.fe.util
from grouper.models import AsyncNotification, Group, Permission, User
from grouper.permissions import (
        get_owners,
        get_owners_by_grantable_permission,
        get_requests_by_owner,
        )
from url_util import url


@pytest.fixture
def grantable_permissions(session, standard_graph):
    perm_grant, _ = Permission.get_or_create(session, name=PERMISSION_GRANT, description="")
    perm0, _ = Permission.get_or_create(session, name="grantable", description="")
    perm1, _ = Permission.get_or_create(session, name="grantable.one", description="")
    perm2, _ = Permission.get_or_create(session, name="grantable.two", description="")
    session.commit()

    return perm_grant, perm0, perm1, perm2


def test_basic_permission(standard_graph, session, users, groups, permissions):  # noqa
    """ Test adding some permissions to various groups and ensuring that the permissions are all
        implemented as expected. This also tests permissions inheritance in the graph. """

    graph = standard_graph  # noqa

    assert sorted(get_group_permissions(graph, "team-sre")) == ["audited:", "ssh:*", "sudo:shell"]
    assert sorted(get_group_permissions(graph, "tech-ops")) == [
        "audited:", "ssh:shell", "sudo:shell"]
    assert sorted(get_group_permissions(graph, "team-infra")) == ["sudo:shell"]
    assert sorted(get_group_permissions(graph, "all-teams")) == []

    assert sorted(get_user_permissions(graph, "gary@a.co")) == [
        "audited:", "ssh:*", "ssh:shell", "sudo:shell"]
    assert sorted(get_user_permissions(graph, "zay@a.co")) == [
        "audited:", "ssh:*", "ssh:shell", "sudo:shell"]
    assert sorted(get_user_permissions(graph, "zorkian@a.co")) == [
        "audited:", AUDIT_MANAGER + ":", PERMISSION_AUDITOR + ":", "ssh:*", "sudo:shell"]
    assert sorted(get_user_permissions(graph, "testuser@a.co")) == []
    assert sorted(get_user_permissions(graph, "figurehead@a.co")) == [
        "sudo:shell"]


def test_has_permission(standard_graph, users):  # noqa
    """ Tests the has_permission method of a user object. """

    # In our setup, zorkian has 'audited' with no arguments
    assert users["zorkian@a.co"].has_permission("audited"), "zorkian has permission audited"
    assert not users["zorkian@a.co"].has_permission("audited", argument='foo'), \
        "zorkian has permission audited:foo"
    assert not users["zorkian@a.co"].has_permission("audited", argument='*'), \
        "zorkian has permission audited:*"

    # zay has ssh:*
    assert users["zay@a.co"].has_permission("ssh"), "zay has permission ssh"
    assert users["zay@a.co"].has_permission("ssh", argument='foo'), "zay has permission ssh:foo"
    assert users["zay@a.co"].has_permission("ssh", argument='*'), "zay has permission ssh:*"


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
        self.assertRaises(ValidationError, eval_argument, 'whitespace invalid')
        self.assertRaises(ValidationError, eval_argument, 'question?mark')
        self.assertRaises(ValidationError, eval_argument, 'exclaimation!point')


def test_grantable_permissions(session, standard_graph, users, groups, grantable_permissions):
    perm_grant, perm0, _, _ = grantable_permissions

    assert not users["zorkian@a.co"].my_grantable_permissions(), "start with none"

    grant_permission(groups["auditors"], perm_grant, argument="notgrantable.one")
    assert not users["zorkian@a.co"].my_grantable_permissions(), "grant on non-existent is fine"

    grant_permission(groups["auditors"], perm_grant, argument=perm0.name)
    grants = users["zorkian@a.co"].my_grantable_permissions()
    assert len(grants) == 1, "only specific permission grant"
    assert grants[0][0].name == perm0.name, "only specific permission grant"

    grant_permission(groups["auditors"], perm_grant, argument="grantable.*")
    grants = users["zorkian@a.co"].my_grantable_permissions()
    assert len(grants) == 3, "wildcard grant should grab appropriat amount"
    assert sorted([x[0].name for x in grants]) == ["grantable", "grantable.one", "grantable.two"]


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
    res = get_owners(session, perm1, "somesubstring", owners_by_arg_by_perm=owners_by_arg_by_perm)
    assert (sorted(res) == sorted([groups["all-teams"], groups["team-sre"]]),
            "should include substring wildcard matches")

    res = get_owners(session, perm1, "othersubstring", owners_by_arg_by_perm=owners_by_arg_by_perm)
    assert sorted(res) == [groups["all-teams"]], "negative test of substring wildcard matches"


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

    # REQUEST: 'grantable.one', 'some argument' for 'serving-team'
    groupname = "serving-team"
    username = "zorkian@a.co"
    fe_url = url(base_url, "/groups/{}/permission/request".format(groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"permission_name": "grantable.one", "argument": "some argument",
                "reason": "blah blah black sheep"}),
            headers={'X-Grouper-User': username})
    assert resp.code == 200

    emails = session.query(AsyncNotification).all()
    assert len(emails) == 1, "only one user (and no group) should receive notification for request"

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

    emails = session.query(AsyncNotification).all()
    assert len(emails) == 2, "requester should receive email as well"

    # (re)REQUEST: 'grantable.one', 'some argument' for 'serving-team'
    groupname = "serving-team"
    username = "zorkian@a.co"
    fe_url = url(base_url, "/groups/{}/permission/request".format(groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"permission_name": "grantable.one", "argument": "some argument",
                "reason": "blah blah black sheep"}),
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
                "reason": "blah blah black sheep"}),
            headers={'X-Grouper-User': username})
    assert resp.code == 200

    emails = session.query(AsyncNotification).all()
    assert len(emails) == 3, "only one user (and no group) should receive notification for request"

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

    emails = session.query(AsyncNotification).all()
    assert len(emails) == 4, "rejection email should be sent"

    perms = _load_permissions_by_group_name(session, 'serving-team')
    assert len(perms) == 2
    assert "grantable.two" not in perms, "no new permissions should be granted for this"
