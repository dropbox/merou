import re
import unittest

import grouper.fe.util

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from util import get_group_permissions, get_user_permissions

from grouper.constants import PERMISSION_AUDITOR, PERMISSION_VALIDATION


def test_basic_permission(standard_graph, session, users, groups, permissions):  # noqa
    """ Test adding some permissions to various groups and ensuring that the permissions are all
        implemented as expected. This also tests permissions inheritance in the graph. """

    graph = standard_graph  # noqa

    assert sorted(get_group_permissions(graph, "team-sre")) == ["audited:", "ssh:*", "sudo:shell"]
    assert sorted(get_group_permissions(graph, "tech-ops")) == [
        "audited:", "ssh:shell", "sudo:shell"]
    assert sorted(get_group_permissions(graph, "team-infra")) == ["sudo:shell"]
    assert sorted(get_group_permissions(graph, "all-teams")) == []

    assert sorted(get_user_permissions(graph, "gary")) == [
        "audited:", "ssh:*", "ssh:shell", "sudo:shell"]
    assert sorted(get_user_permissions(graph, "zay")) == [
        "audited:", "ssh:*", "ssh:shell", "sudo:shell"]
    assert sorted(get_user_permissions(graph, "zorkian")) == [
        "audited:", PERMISSION_AUDITOR + ":", "ssh:*", "sudo:shell"]
    assert sorted(get_user_permissions(graph, "testuser")) == []


class PermissionTests(unittest.TestCase):
    def test_reject_bad_permission_names(self):
        self.assertEquals(len(grouper.fe.util.test_reserved_names("permission_lacks_period")), 1)
        self.assertEquals(len(grouper.fe.util.test_reserved_names("grouper.prefix.reserved")), 1)
        self.assertEquals(len(grouper.fe.util.test_reserved_names("admin.prefix.reserved")), 1)
        self.assertEquals(len(grouper.fe.util.test_reserved_names("test.prefix.reserved")), 1)

        def eval_permission(perm):
            return re.match(r'^' + PERMISSION_VALIDATION + r'$', perm)

        self.assertIsNotNone(eval_permission('foo.bar'))
        self.assertIsNotNone(eval_permission('foobar'))
        self.assertIsNotNone(eval_permission('foo.bar_baz'))
        self.assertIsNone(eval_permission('foo__bar'))
        self.assertIsNone(eval_permission('foo.bar.'))
        self.assertIsNone(eval_permission('foo._bar'))
