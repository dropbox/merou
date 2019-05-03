from datetime import datetime
from time import time
from typing import TYPE_CHECKING

import pytest

from grouper.email_util import notify_edge_expiration, UnknownActorDuringExpirationException
from grouper.models.group_edge import GroupEdge
from grouper.settings import Settings

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_actor_for_edge_expiration(setup):
    # type: (SetupTest) -> None
    """Test choice of actor ID when expiring an edge.

    Our current audit log model has no concept of a system-generated change and has to map every
    change to a user ID that performed that change.  We previously had a bug where we would try to
    grab the first owner of the group and use them as the actor when someone expired out of a
    group, which caused uncaught exceptions if the group somehow ended up in a state with no
    owners.  Test that we do something sane when expiring edges if possible.

    Everything we're testing here is a workaround for a bug.  Once the audit log has been fixed so
    that we can log entries for system actions without attributing them to some user in the system,
    this test and all of the logic it's testing can go away.
    """
    settings = Settings()
    now_minus_one_second = datetime.utcfromtimestamp(int(time() - 1))
    audit_log_service = setup.service_factory.create_audit_log_service()

    # An expiring individual user should be logged with an actor ID of the user.
    with setup.transaction():
        setup.add_user_to_group("user@a.co", "some-group", expiration=now_minus_one_second)
    edge = setup.session.query(GroupEdge).filter_by(expiration=now_minus_one_second).one()
    notify_edge_expiration(settings, setup.session, edge)
    log_entries = audit_log_service.entries_affecting_user("user@a.co", 1)
    assert log_entries
    assert log_entries[0].actor == "user@a.co"
    assert log_entries[0].action == "expired_from_group"
    assert log_entries[0].on_user == "user@a.co"
    with setup.transaction():
        edge.delete(setup.session)

    # An expiring group should be logged with an actor ID of the owner of the parent group.
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "parent-group", role="owner")
        setup.add_user_to_group("zorkian@a.co", "child-group", role="owner")
        setup.add_group_to_group("child-group", "parent-group", expiration=now_minus_one_second)
    edge = setup.session.query(GroupEdge).filter_by(expiration=now_minus_one_second).one()
    notify_edge_expiration(settings, setup.session, edge)
    log_entries = audit_log_service.entries_affecting_group("child-group", 1)
    assert log_entries
    assert log_entries[0].actor == "gary@a.co"
    assert log_entries[0].action == "expired_from_group"
    assert log_entries[0].on_group == "child-group"
    log_entries = audit_log_service.entries_affecting_group("parent-group", 1)
    assert log_entries
    assert log_entries[0].actor == "gary@a.co"
    assert log_entries[0].action == "expired_from_group"
    assert log_entries[0].on_group == "parent-group"
    with setup.transaction():
        edge.delete(setup.session)

    # If the parent group has no owner, it should be logged with an actor ID of the owner of the
    # child group.
    with setup.transaction():
        setup.add_user_to_group("zorkian@a.co", "a-group", role="owner")
        setup.add_group_to_group("a-group", "ownerless-group", expiration=now_minus_one_second)
    edge = setup.session.query(GroupEdge).filter_by(expiration=now_minus_one_second).one()
    notify_edge_expiration(settings, setup.session, edge)
    log_entries = audit_log_service.entries_affecting_group("a-group", 1)
    assert log_entries
    assert log_entries[0].actor == "zorkian@a.co"
    assert log_entries[0].action == "expired_from_group"
    assert log_entries[0].on_group == "a-group"
    log_entries = audit_log_service.entries_affecting_group("ownerless-group", 1)
    assert log_entries
    assert log_entries[0].actor == "zorkian@a.co"
    assert log_entries[0].action == "expired_from_group"
    assert log_entries[0].on_group == "ownerless-group"
    with setup.transaction():
        edge.delete(setup.session)

    # If neither group has an owner, raise an exception.
    with setup.transaction():
        setup.add_group_to_group("other-group", "ownerless-group", expiration=now_minus_one_second)
    edge = setup.session.query(GroupEdge).filter_by(expiration=now_minus_one_second).one()
    with pytest.raises(UnknownActorDuringExpirationException):
        notify_edge_expiration(settings, setup.session, edge)
