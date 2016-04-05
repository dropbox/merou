from fixtures import graph, groups, permissions, session, standard_graph, users

from grouper.model_soup import Group, Request, User
from util import add_member


def test_basic_request(graph, groups, permissions, session, standard_graph, users):
    group_sre = groups["team-sre"]
    group_not_sre = [g for name,g in groups.items() if name != "team-sre"]

    assert not any([group.my_requests(status="pending").all() for group in groups.values()]), \
            "no group should start with pending requests"

    group_sre.add_member(users["testuser@a.co"], users["testuser@a.co"], reason="for the lulz")
    session.commit()

    request_not_sre = [group.my_requests(status="pending").all() for group in group_not_sre]
    assert not any(request_not_sre), "only affected group should show pending requests"
    request_sre = group_sre.my_requests(status="pending").all()
    assert len(request_sre) == 1, "affected group should have request"

    request = session.query(Request).filter_by(id=request_sre[0].id).scalar()
    request.update_status(users["gary@a.co"], "actioned", "for being a good person")
    session.commit()

    assert not any([group.my_requests(status="pending").all() for group in groups.values()]), \
            "no group should have requests after being actioned"

def test_aggregate_request(graph, groups, permissions, session, standard_graph, users):
    gary = users["gary@a.co"]
    testuser = users["testuser@a.co"]
    not_involved = [user for name,user in users.items() if name not in ("gary@a.co",
            "testuser@a.co")]

    assert not any([u.my_requests_aggregate().all() for u in users.values()]), \
            "should have no pending requests to begin with"

    # one request to one team
    groups["team-sre"].add_member(users["testuser@a.co"], users["testuser@a.co"],
            reason="for the lulz")
    session.commit()

    assert len(gary.my_requests_aggregate().all()) == 1, "one pending request for owner"
    assert not any([u.my_requests_aggregate().all() for u in not_involved]), \
            "no pending requests if you're not the owner"

    # two request to two teams, same owner
    groups["team-infra"].add_member(users["testuser@a.co"], users["testuser@a.co"],
            reason="for the lulz")
    session.commit()

    request_gary = gary.my_requests_aggregate().all()
    assert len(request_gary) == 2, "two pending request for owner"
    assert not any([u.my_requests_aggregate().all() for u in not_involved]), \
            "no pending requests if you're not the owner"

    # resolving one request should reflect
    request = session.query(Request).filter_by(id=request_gary[0].id).scalar()
    request.update_status(users["gary@a.co"], "actioned", "for being a good person")
    session.commit()

    assert len(gary.my_requests_aggregate().all()) == 1, "one pending request for owner"
    assert not any([u.my_requests_aggregate().all() for u in not_involved]), \
            "no pending requests if you're not the owner"

    # requests to dependent teams should reflect apprpriately
    groups["security-team"].add_member(users["testuser@a.co"], users["testuser@a.co"],
            reason="for the lulz")
    session.commit()

    assert len(gary.my_requests_aggregate().all()) == 1, "super owner should not get request"
    assert len(users["oliver@a.co"].my_requests_aggregate().all()) == 1, "owner should get request"
    user_not_gary_oliver = [u for n,u in users.items() if n not in ("gary@a.co","oliver@a.co")]
    assert not any([u.my_requests_aggregate().all() for u in user_not_gary_oliver])

    # manager and np-owner should get requests
    figurehead = users["figurehead@a.co"]
    add_member(groups["audited-team"], figurehead, role="manager")
    assert len(figurehead.my_requests_aggregate().all()) == 0, "no request for np-owner at first"

    groups["tech-ops"].add_member(users["testuser@a.co"], users["testuser@a.co"],
            reason="for the lulz")
    assert len(figurehead.my_requests_aggregate().all()) == 1, "request for np-owner"

    groups["audited-team"].add_member(users["testuser@a.co"], users["testuser@a.co"],
            reason="for the lulz")
    assert len(figurehead.my_requests_aggregate().all()) == 2, "request for np-owner and manager"
