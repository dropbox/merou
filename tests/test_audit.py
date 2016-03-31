from collections import namedtuple
from datetime import datetime, timedelta
from urllib import urlencode

import pytest

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from grouper.audit import (
    assert_can_join, assert_controllers_are_auditors, get_audits, user_is_auditor,
    UserNotAuditor,
)
from url_util import url
from util import add_member, grant_permission
from grouper.models.audit_log import AuditLogCategory, AuditLog


def test_group_audited(standard_graph, session, groups, permissions):  # noqa
    """ Ensure that the audited flag gets set appropriate only groups and inherited down the
        graph. """

    graph = standard_graph  # noqa

    assert not graph.get_group_details("security-team")["audited"]
    assert graph.get_group_details("serving-team")["audited"]
    assert graph.get_group_details("team-sre")["audited"]


def test_user_is_auditor(standard_graph):  # noqa
    """ Ensure users get the ability to audit. """

    assert user_is_auditor("zorkian@a.co")
    assert not user_is_auditor("oliver@a.co")


def test_assert_can_join(users, groups):  # noqa
    """ Test various audit constraints to ensure that users can/can't join as appropriate. """

    # Non-auditor can join non-audited group as owner.
    assert assert_can_join(groups["team-infra"], users["zay@a.co"], role="owner")

    # Auditor can join non-audited group as owner.
    assert assert_can_join(groups["team-infra"], users["zorkian@a.co"], role="owner")

    # Non-auditor can NOT join audited group as owner.
    with pytest.raises(UserNotAuditor):
        assert not assert_can_join(groups["serving-team"], users["zay@a.co"], role="owner")

    # Non-auditor can join audited group as member.
    assert assert_can_join(groups["serving-team"], users["zay@a.co"])

    # Group with non-auditor owner can NOT join audited group.
    with pytest.raises(UserNotAuditor):
        assert not assert_can_join(groups["serving-team"], groups["tech-ops"])

    # Group with auditor owner can join audited group.
    assert assert_can_join(groups["serving-team"], groups["sad-team"])

    # Group with non-auditor owner can join non-audited group.
    assert assert_can_join(groups["team-infra"], groups["tech-ops"])

    # Group with auditor owner, but sub-group with non-auditor owner, can NOT join audited group.
    with pytest.raises(UserNotAuditor):
        assert not assert_can_join(groups["audited-team"], groups["serving-team"])


def test_assert_controllers_are_auditors(groups):  # noqa
    """ Test the method that determines if a subtree is controlled by auditors. """

    # Group is safely controlled by auditors.
    assert assert_controllers_are_auditors(groups["sad-team"])

    # Group with non-auditor owner should fail this test.
    with pytest.raises(UserNotAuditor):
        assert not assert_controllers_are_auditors(groups["team-infra"])


@pytest.mark.gen_test
def test_audit_end_to_end(session, users, groups, http_client, base_url):  # noqa
    """ Tests an end-to-end audit cycle. """
    groupname = 'audited-team'

    zay_id = users["zay@a.co"].id
    gary_id = users["gary@a.co"].id

    # make everyone an auditor or global audit will have issues
    add_member(groups["auditors"], users["gary@a.co"])
    add_member(groups["auditors"], users["oliver@a.co"])
    add_member(groups["auditors"], users["zay@a.co"])
    add_member(groups["auditors"], users["figurehead@a.co"])

    # add some users to test removal
    add_member(groups[groupname], users["zay@a.co"])
    add_member(groups[groupname], users["gary@a.co"])

    # start the audit
    end_at_str = (datetime.now() + timedelta(days=10)).strftime('%m/%d/%Y')
    fe_url = url(base_url, '/audits/create')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'ends_at': end_at_str}), headers={'X-Grouper-User': 'zorkian@a.co'})
    assert resp.code == 200

    open_audits = get_audits(session, only_open=True).all()
    assert len(open_audits) == 4, 'audits created'

    assert groupname in [x.group.name for x in open_audits], 'group we expect also gets audit'

    # pull all the info we need to resolve audits, avoids detached sqlalchemy sessions
    AuditMember = namedtuple('AuditMember', 'am_id, edge_type, edge_id')
    Audit = namedtuple('Audit', 'audit_id, owner_name, group_name, audit_members')
    all_group_ids = [x.group.id for x in open_audits]
    open_audits = [Audit(x.id, x.group.my_owners().iterkeys().next(), x.group.name,
            [AuditMember(am.id, am.edge.member_type, am.edge_id) for am in x.my_members()]) for
            x in open_audits]

    # approve everything but the one we added members to
    for one_audit in open_audits:
        fe_url = url(base_url, '/audits/{}/complete'.format(one_audit.audit_id))

        if one_audit.group_name == groupname:
            continue

        # blanket approval
        body = urlencode({"audit_{}".format(am.am_id): "approved" for am in
                one_audit.audit_members})

        resp = yield http_client.fetch(fe_url, method="POST", body=body,
                headers={'X-Grouper-User': one_audit.owner_name})
        assert resp.code == 200

    open_audits = get_audits(session, only_open=True).all()
    assert len(open_audits) == 1, 'only our test group remaining'

    one_audit = open_audits[0]
    one_audit.id

    body_dict = {}
    for am in one_audit.my_members():
        if gary_id == am.member.id:
            # deny
            body_dict["audit_{}".format(am.id)] = "remove"
        else:
            # approve
            body_dict["audit_{}".format(am.id)] = "approved"

    owner_name = one_audit.group.my_owners().iterkeys().next()
    fe_url = url(base_url, '/audits/{}/complete'.format(one_audit.id))
    resp = yield http_client.fetch(fe_url, method="POST", body=urlencode(body_dict),
            headers={'X-Grouper-User': owner_name})
    assert resp.code == 200

    # check all the logs
    assert len(AuditLog.get_entries(session, action='start_audit')) == 1, 'global start is logged'
    assert len(AuditLog.get_entries(session,
            action='complete_global_audit')) == 1, 'global complete is logged'

    for group_id in all_group_ids:
        assert len(AuditLog.get_entries(session, on_group_id=group_id, action='complete_audit',
                category=AuditLogCategory.audit)) == 1, 'complete entry for each group'

    assert len(AuditLog.get_entries(session, on_user_id=gary_id,
            category=AuditLogCategory.audit)) == 1, 'removal AuditLog entry on user'
