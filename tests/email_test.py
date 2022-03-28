from datetime import datetime

import pytest
from mock import patch

from grouper.background.background_processor import BackgroundProcessor
from grouper.background.settings import BackgroundSettings
from grouper.models.async_notification import AsyncNotification
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.settings import set_global_settings
from tests.fixtures import (  # noqa: F401
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)
from tests.util import add_member, get_users, revoke_member


def _get_unsent_emails_and_send(session):  # noqa: F811
    """Helper to count unsent emails and then mark them as sent."""
    emails = session.query(AsyncNotification).filter_by(sent=False).all()

    for email in emails:
        email.sent = True

    session.commit()
    return emails


@pytest.fixture
def expired_graph(session, graph, groups, users):  # noqa: F811
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


def test_expire_edges(expired_graph, session):  # noqa: F811
    """Test expiration auditing and notification."""
    email = session.query(AsyncNotification).all()
    assert email == []
    for edge in session.query(GroupEdge).all():
        assert edge.active == True

    # Expire the edges.
    settings = BackgroundSettings()
    set_global_settings(settings)
    background = BackgroundProcessor(settings, None)
    background.expire_edges(session)

    # Check that the edges are now marked as inactive.
    edges = (
        session.query(GroupEdge)
        .filter(
            GroupEdge.group_id == Group.id, Group.enabled == True, GroupEdge.expiration != None
        )
        .all()
    )
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


@patch("grouper.audit.get_auditors_group_name", return_value="auditors")
def test_promote_nonauditors(
    mock_gagn, standard_graph, graph, users, groups, session, permissions  # noqa: F811
):
    """Test expiration auditing and notification."""

    assert graph.get_group_details("audited-team")["audited"]

    #
    # Ensure auditors promotion for all approvers
    #
    approver_roles = ["owner", "np-owner", "manager"]

    affected_users = set(["figurehead@a.co", "gary@a.co", "testuser@a.co", "zay@a.co"])
    for idx, role in enumerate(approver_roles):

        # Add non-auditor as an approver to an audited group
        add_member(groups["audited-team"], users["testuser@a.co"], role=role)
        graph.update_from_db(session)
        assert not affected_users.intersection(get_users(graph, "auditors"))

        # do the promotion logic
        settings = BackgroundSettings()
        set_global_settings(settings)
        background = BackgroundProcessor(settings, None)
        background.promote_nonauditors(session)

        # Check that the users now added to auditors group
        graph.update_from_db(session)
        assert affected_users.intersection(get_users(graph, "auditors")) == affected_users
        unsent_emails = _get_unsent_emails_and_send(session)
        assert any(
            [
                'Subject: Added as member to group "auditors"' in email.body
                and "To: testuser@a.co" in email.body
                for email in unsent_emails
            ]
        )
        assert any(
            [
                'Subject: Added as member to group "auditors"' in email.body
                and "To: gary@a.co" in email.body
                for email in unsent_emails
            ]
        )
        assert any(
            [
                'Subject: Added as member to group "auditors"' in email.body
                and "To: zay@a.co" in email.body
                for email in unsent_emails
            ]
        )

        audits = AuditLog.get_entries(session, action="nonauditor_promoted")
        assert len(audits) == len(affected_users) * (idx + 1)

        # reset for next iteration
        revoke_member(groups["audited-team"], users["testuser@a.co"])
        for username in affected_users:
            revoke_member(groups["auditors"], users[username])

    #
    # Ensure nonauditor, nonapprovers in audited groups do not get promoted
    #

    # first, run a promotion to get any other promotion that we don't
    # care about out of the way
    background = BackgroundProcessor(settings, None)
    background.promote_nonauditors(session)

    prev_audit_log_count = len(AuditLog.get_entries(session, action="nonauditor_promoted"))

    member_roles = ["member"]
    for idx, role in enumerate(member_roles):

        # Add non-auditor as a non-approver to an audited group
        add_member(groups["audited-team"], users["testuser@a.co"], role=role)

        # do the promotion logic
        background = BackgroundProcessor(settings, None)
        background.promote_nonauditors(session)

        # Check that the user is not added to auditors group
        graph.update_from_db(session)
        assert "testuser@a.co" not in get_users(graph, "auditors")

        assert not any(
            [
                'Subject: Added as member to group "auditors"' in email.body
                and "To: testuser@a.co" in email.body
                for email in _get_unsent_emails_and_send(session)
            ]
        )

        audits = AuditLog.get_entries(session, action="nonauditor_promoted")
        assert len(audits) == prev_audit_log_count

        revoke_member(groups["audited-team"], users["testuser@a.co"])
