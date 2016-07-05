from datetime import datetime, timedelta
import pytest

from fixtures import graph, users, groups, session, permissions, standard_graph  # noqa
from util import add_member, revoke_member

from grouper.background import BackgroundThread
from grouper.fe.settings import settings
from grouper.model_soup import AsyncNotification, Group, GroupEdge
from grouper.models.audit_log import AuditLog


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
    background = BackgroundThread(settings, None)
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


def test_expire_nonauditors(standard_graph, users, groups, session, permissions):
    """ Test expiration auditing and notification. """

    graph = standard_graph  # noqa

    # Test audit autoexpiration for all approvers

    approver_roles = ["owner", "np-owner", "manager"]

    for role in approver_roles:

        # Add non-auditor as an owner to an audited group
        add_member(groups["audited-team"], users["testuser@a.co"], role=role)
        session.commit()
        graph.update_from_db(session)

        group_md = graph.get_group_details("audited-team")

        assert group_md.get('audited', False)

        # Expire the edges.
        background = BackgroundThread(settings, None)
        background.expire_nonauditors(session)

        # Check that the edges are now marked as inactive.
        edge = session.query(GroupEdge).filter_by(group_id=groups["audited-team"].id, member_pk=users["testuser@a.co"].id).scalar()
        assert edge.expiration is not None
        assert edge.expiration < datetime.utcnow() + timedelta(days=settings.nonauditor_expiration_days)
        assert edge.expiration > datetime.utcnow() + timedelta(days=settings.nonauditor_expiration_days - 1)

        assert any(["Subject: Membership in audited-team set to expire" in email.body and "To: testuser@a.co" in email.body for email in _get_unsent_emails_and_send(session)])

        audits = AuditLog.get_entries(session, action="nonauditor_flagged")
        assert len(audits) == 3 + 1 * (approver_roles.index(role) + 1)

        revoke_member(groups["audited-team"], users["testuser@a.co"])

    # Ensure nonauditor, nonapprovers in audited groups do not get set to expired

    member_roles = ["member"]

    for role in member_roles:

        # Add non-auditor as an owner to an audited group
        add_member(groups["audited-team"], users["testuser@a.co"], role=role)
        session.commit()
        graph.update_from_db(session)

        group_md = graph.get_group_details("audited-team")

        assert group_md.get('audited', False)

        # Expire the edges.
        background = BackgroundThread(settings, None)
        background.expire_nonauditors(session)

        # Check that the edges are now marked as inactive.
        edge = session.query(GroupEdge).filter_by(group_id=groups["audited-team"].id, member_pk=users["testuser@a.co"].id).scalar()
        assert edge.expiration is None

        assert not any(["Subject: Membership in audited-team set to expire" in email.body and "To: testuser@a.co" in email.body for email in _get_unsent_emails_and_send(session)])

        audits = AuditLog.get_entries(session, action="nonauditor_flagged")
        assert len(audits) == 3 + 1 * len(approver_roles)

        revoke_member(groups["audited-team"], users["testuser@a.co"])
