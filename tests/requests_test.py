from grouper.group_requests import get_requests_by_group
from grouper.models.request import Request
from grouper.role_user import is_role_user
from grouper.user import user_requests_aggregate
from tests.fixtures import (  # noqa: F401
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)
from tests.util import add_member


def test_basic_request(graph, groups, permissions, session, standard_graph, users):  # noqa: F811
    group_sre = groups["team-sre"]
    group_not_sre = [g for name, g in groups.items() if name != "team-sre"]

    assert not any(
        [
            get_requests_by_group(session, group, status="pending").all()
            for group in groups.values()
            if not is_role_user(session, group=group)
        ]
    ), "no group should start with pending requests"

    group_sre.add_member(users["testuser@a.co"], users["testuser@a.co"], reason="for the lulz")
    session.commit()

    request_not_sre = [
        get_requests_by_group(session, group, status="pending").all() for group in group_not_sre
    ]
    assert not any(request_not_sre), "only affected group should show pending requests"
    request_sre = get_requests_by_group(session, group_sre, status="pending").all()
    assert len(request_sre) == 1, "affected group should have request"

    request = session.query(Request).filter_by(id=request_sre[0].id).scalar()
    request.update_status(users["gary@a.co"], "actioned", "for being a good person")
    session.commit()

    assert not any(
        [
            get_requests_by_group(session, group, status="pending").all()
            for group in groups.values()
        ]
    ), "no group should have requests after being actioned"


def test_aggregate_request(
    graph, groups, permissions, session, standard_graph, users  # noqa: F811
):
    gary = users["gary@a.co"]
    not_involved = [
        user for name, user in users.items() if name not in ("gary@a.co", "testuser@a.co")
    ]

    assert not any(
        [user_requests_aggregate(session, u).all() for u in users.values()]
    ), "should have no pending requests to begin with"

    # one request to one team
    groups["team-sre"].add_member(
        users["testuser@a.co"], users["testuser@a.co"], reason="for the lulz"
    )
    session.commit()

    assert len(user_requests_aggregate(session, gary).all()) == 1, "one pending request for owner"
    assert not any(
        [user_requests_aggregate(session, u).all() for u in not_involved]
    ), "no pending requests if you're not the owner"

    # two request to two teams, same owner
    groups["team-infra"].add_member(
        users["testuser@a.co"], users["testuser@a.co"], reason="for the lulz"
    )
    session.commit()

    request_gary = user_requests_aggregate(session, gary).all()
    assert len(request_gary) == 2, "two pending request for owner"
    assert not any(
        [user_requests_aggregate(session, u).all() for u in not_involved]
    ), "no pending requests if you're not the owner"

    # resolving one request should reflect
    request = session.query(Request).filter_by(id=request_gary[0].id).scalar()
    request.update_status(users["gary@a.co"], "actioned", "for being a good person")
    session.commit()

    assert len(user_requests_aggregate(session, gary).all()) == 1, "one pending request for owner"
    assert not any(
        [user_requests_aggregate(session, u).all() for u in not_involved]
    ), "no pending requests if you're not the owner"

    # requests to dependent teams should reflect apprpriately
    groups["security-team"].add_member(
        users["testuser@a.co"], users["testuser@a.co"], reason="for the lulz"
    )
    session.commit()

    assert (
        len(user_requests_aggregate(session, gary).all()) == 1
    ), "super owner should not get request"
    assert (
        len(user_requests_aggregate(session, users["oliver@a.co"]).all()) == 1
    ), "owner should get request"
    user_not_gary_oliver = [u for n, u in users.items() if n not in ("gary@a.co", "oliver@a.co")]
    assert not any([user_requests_aggregate(session, u).all() for u in user_not_gary_oliver])

    # manager and np-owner should get requests
    figurehead = users["figurehead@a.co"]
    add_member(groups["audited-team"], figurehead, role="manager")
    assert (
        len(user_requests_aggregate(session, figurehead).all()) == 0
    ), "no request for np-owner at first"

    groups["tech-ops"].add_member(
        users["testuser@a.co"], users["testuser@a.co"], reason="for the lulz"
    )
    assert len(user_requests_aggregate(session, figurehead).all()) == 1, "request for np-owner"

    groups["audited-team"].add_member(
        users["testuser@a.co"], users["testuser@a.co"], reason="for the lulz"
    )
    assert (
        len(user_requests_aggregate(session, figurehead).all()) == 2
    ), "request for np-owner and manager"
