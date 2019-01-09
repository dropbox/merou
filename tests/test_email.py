import pytest

from datetime import datetime, timedelta
from mock import call, patch

from fixtures import graph, users, groups, service_accounts, session, permissions, standard_graph  # noqa
from grouper.constants import PERMISSION_AUDITOR
from grouper.background.background_processor import BackgroundProcessor
from grouper.models.async_notification import AsyncNotification
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.settings import settings
from util import add_member, get_users, revoke_member


def _get_unsent_emails_and_send(session):
    """Helper to count unsent emails and then mark them as sent."""
    emails = session.query(AsyncNotification).filter_by(sent=False).all()

    for email in emails:
        email.sent = True

    session.commit()
    return emails


@pytest.fixture
def expired_graph(session, graph, groups, users):
    now = datetime.utcnow()

    # expired user membership
    add_member(groups["team-sre"], users["gary@a.co"], role="owner")
    add_member(groups["team-sre"], users["zay@a.co"], expiration=now)

    # expired group membership
    add_member(groups["serving-team"], users["zorkian@a.co"], role="owner")
    add_member(groups["serving-team"], groups["team-sre"], expiration=now)

    # expired user membership in disabled group
    add_member(groups["sad-team"], users["figurehead@a.co"], expiration=now)
    groups["sad-team"].disable()
    session.commit()

    return graph


def test_expire_edges(expired_graph, session):  # noqa
    """ Test expiration auditing and notification. """
    email = session.query(AsyncNotification).all()
    assert email == []
    for edge in session.query(GroupEdge).all():
        assert edge.active == True

    # Expire the edges.
    background = BackgroundProcessor(settings, None)
    background.expire_edges(session)

    # Check that the edges are now marked as inactive.
    edges = session.query(GroupEdge).filter(
            GroupEdge.group_id == Group.id,
            Group.enabled == True,
            GroupEdge.expiration != None
            ).all()
    for edge in edges:
        assert edge.active == False

    # Check that we have two queued email messages.
    #
    # TODO(rra): It would be nice to check the contents as well.
    email = session.query(AsyncNotification).all()
    assert len(email) == 2

    # Check that we have three audit log entries: one for the expired user and
    # two for both "sides" of the expired group membership.
    audits = AuditLog.get_entries(session, action="expired_from_group")
    assert len(audits) == 3


@patch('grouper.audit.get_auditors_group_name', return_value='auditors')
def test_promote_nonauditors(mock_gagn, standard_graph, users, groups, session, permissions):
    """ Test expiration auditing and notification. """

    graph = standard_graph  # noqa

    assert graph.get_group_details("audited-team")['audited']

    # Test auditors promotion for all approvers
    approver_roles = ["owner", "np-owner", "manager"]

    for role in approver_roles:

        # Add non-auditor as an approver to an audited group
        add_member(groups["audited-team"], users["testuser@a.co"], role=role)
        session.commit()
        graph.update_from_db(session)
        assert "testuser@a.co" not in get_users(graph, "auditors")

        # do the promotion logic
        background = BackgroundProcessor(settings, None)
        background.promote_nonauditors(session)

        session.commit()
        graph.update_from_db(session)

        # Check that the user is now added to auditors group
        assert "testuser@a.co" in get_users(graph, "auditors")
        assert any(["Subject: Added as member to group \"auditors\"" in email.body and "To: testuser@a.co" in email.body for email in _get_unsent_emails_and_send(session)])

        audits = AuditLog.get_entries(session, action="nonauditor_promoted")
        assert len(audits) == 3 + 1 * (approver_roles.index(role) + 1)

        # reset for next iteration
        revoke_member(groups["audited-team"], users["testuser@a.co"])
        revoke_member(groups["auditors"], users["testuser@a.co"])

    # Ensure nonauditor, nonapprovers in audited groups do not get promoted
    member_roles = ["member"]

    for role in member_roles:

        # Add non-auditor as a non-approver to an audited group
        add_member(groups["audited-team"], users["testuser@a.co"], role=role)
        session.commit()
        graph.update_from_db(session)
        assert "testuser@a.co" not in get_users(graph, "auditors")

        # do the promotion logic
        background = BackgroundProcessor(settings, None)
        background.promote_nonauditors(session)

        session.commit()
        graph.update_from_db(session)

        # Check that the user is not added to auditors group
        assert "testuser@a.co" not in get_users(graph, "auditors")

        assert not any(["Subject: Added as member to group \"auditors\"" in email.body and "To: testuser@a.co" in email.body for email in _get_unsent_emails_and_send(session)])

        audits = AuditLog.get_entries(session, action="nonauditor_promoted")
        assert len(audits) == 3 + 1 * len(approver_roles)

        revoke_member(groups["audited-team"], users["testuser@a.co"])
        revoke_member(groups["auditors"], users["testuser@a.co"])
