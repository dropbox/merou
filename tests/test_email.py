import pytest

from datetime import datetime, timedelta
from mock import patch

from fixtures import graph, users, groups, service_accounts, session, permissions, standard_graph  # noqa
from grouper.background.background_processor import BackgroundProcessor
from grouper.fe.settings import settings
from grouper.models.async_notification import AsyncNotification
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from util import add_member, revoke_member


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


