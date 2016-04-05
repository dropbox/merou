from datetime import datetime, timedelta
import imp
import unittest

import pytest

from fixtures import graph, session, users, groups, permissions
from util import add_member, edit_member, revoke_member, grant_permission

from grouper.email_util import process_async_emails
from grouper.model_soup import AsyncNotification
from grouper.settings import settings

imp.load_source('grouper-api', 'bin/grouper-api')

@pytest.fixture
def expiring_graph(session, graph, users, groups, permissions):
    now = datetime.utcnow()
    note_exp_now = now + timedelta(settings.expiration_notice_days)
    week = timedelta(7)

    add_member(groups["team-sre"], users["oliver@a.co"], role="owner")
    add_member(groups["team-sre"], users["gary@a.co"], role="owner")
    add_member(groups["team-sre"], users["zay@a.co"], expiration=note_exp_now+week)
    add_member(groups["team-sre"], users["zorkian@a.co"])
    add_member(groups["team-sre"], users["zebu@a.co"], role="owner", expiration=note_exp_now+week)
    revoke_member(groups["team-sre"], users["zebu@a.co"])
    grant_permission(groups["team-sre"], permissions["ssh"], argument="*")

    add_member(groups["serving-team"], users["zorkian@a.co"], role="owner")
    add_member(groups["serving-team"], groups["team-sre"], expiration=note_exp_now+week)
    add_member(groups["serving-team"], groups["tech-ops"])
    grant_permission(groups["serving-team"], permissions["audited"])

    add_member(groups["tech-ops"], users["zay@a.co"], role="owner")
    add_member(groups["tech-ops"], users["gary@a.co"], expiration=note_exp_now+2*week)
    grant_permission(groups["tech-ops"], permissions["ssh"], argument="shell")

    return graph

def test_expiration_notifications(expiring_graph, session, users, groups, permissions):  # noqa
    now = datetime.utcnow()
    note_exp_now = now + timedelta(settings.expiration_notice_days)
    day = timedelta(1)
    week = timedelta(7)

    # What expirations are coming up in the next day?  Next week?
    upcoming_expirations = AsyncNotification._get_unsent_expirations(session, now+day)
    assert upcoming_expirations == []

    upcoming_expirations = AsyncNotification._get_unsent_expirations(session, now+week)
    assert sorted(upcoming_expirations) == [
        # Group, subgroup, subgroup owners.
        ("serving-team", "team-sre", "gary@a.co"),
        ("serving-team", "team-sre", "oliver@a.co"),
        # Group, user, user.
        ("team-sre", "zay@a.co", "zay@a.co"),
    ]

    # Make someone expire a week from now.
    edit_member(groups["team-sre"], users["zorkian@a.co"], expiration=note_exp_now+week)
    upcoming_expirations = AsyncNotification._get_unsent_expirations(session, now+week)
    assert sorted(upcoming_expirations) == [
        # Group, subgroup, subgroup owners.
        ("serving-team", "team-sre", "gary@a.co"),
        ("serving-team", "team-sre", "oliver@a.co"),
        # Group, user, user.
        ("team-sre", "zay@a.co", "zay@a.co"),
        ("team-sre", "zorkian@a.co", "zorkian@a.co"),
    ]

    # Now cancel that expiration.
    edit_member(groups["team-sre"], users["zorkian@a.co"], expiration=None)
    upcoming_expirations = AsyncNotification._get_unsent_expirations(session, now+week)
    assert sorted(upcoming_expirations) == [
        # Group, subgroup, subgroup owners.
        ("serving-team", "team-sre", "gary@a.co"),
        ("serving-team", "team-sre", "oliver@a.co"),
        # Group, user, user.
        ("team-sre", "zay@a.co", "zay@a.co"),
    ]

    # Make an ordinary member an owner.
    edit_member(groups["team-sre"], users["zorkian@a.co"], role="owner")
    upcoming_expirations = AsyncNotification._get_unsent_expirations(session, now+week)
    assert sorted(upcoming_expirations) == [
        # Group, subgroup, subgroup owners.
        ("serving-team", "team-sre", "gary@a.co"),
        ("serving-team", "team-sre", "oliver@a.co"),
        ("serving-team", "team-sre", "zorkian@a.co"),
        # Group, user, user.
        ("team-sre", "zay@a.co", "zay@a.co"),
    ]

    # Make an owner an ordinary member.
    edit_member(groups["team-sre"], users["zorkian@a.co"], role="member")
    upcoming_expirations = AsyncNotification._get_unsent_expirations(session, now+week)
    assert sorted(upcoming_expirations) == [
        # Group, subgroup, subgroup owners.
        ("serving-team", "team-sre", "gary@a.co"),
        ("serving-team", "team-sre", "oliver@a.co"),
        # Group, user, user.
        ("team-sre", "zay@a.co", "zay@a.co"),
    ]

    # Send notices about expirations coming up in the next day, next week.
    notices_sent = process_async_emails(settings, session, now+day, dry_run=True)
    assert notices_sent == 0

    notices_sent = process_async_emails(settings, session, now+week, dry_run=True)
    assert notices_sent == 3
    # ("serving-team", "team-sre", "gary@a.co")
    # ("serving-team", "team-sre", "oliver@a.co")
    # ("team-sre", "zay@a.co", "zay@a.co")

    # Notices in the upcoming week have already been sent, but there's another
    # two weeks from now.
    upcoming_expirations = AsyncNotification._get_unsent_expirations(session, now+week)
    assert upcoming_expirations == []

    upcoming_expirations = AsyncNotification._get_unsent_expirations(session, now+2*week)
    assert upcoming_expirations == [
        ("tech-ops", "gary@a.co", "gary@a.co"),
    ]

    # We already sent these notices.
    notices_sent = process_async_emails(settings, session, now+week, dry_run=True)
    assert notices_sent == 0

    # Extend gary's membership to beyond worth mentioning expiration in two weeks.
    add_member(groups["tech-ops"], users["gary@a.co"], expiration=note_exp_now+3*week)

    upcoming_expirations = AsyncNotification._get_unsent_expirations(session, now+2*week)
    assert upcoming_expirations == []

    notices_sent = process_async_emails(settings, session, now+2*week, dry_run=True)
    assert notices_sent == 0
