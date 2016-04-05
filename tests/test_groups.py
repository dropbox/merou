from datetime import date, timedelta
from urllib import urlencode

import pytest
from tornado.httpclient import HTTPError

from fixtures import fe_app as app
from fixtures import standard_graph, users, graph, groups, session, permissions  # noqa
from grouper.model_soup import Group
from url_util import url
from util import get_users, get_groups, add_member


def setup_desc_to_ances(session, users, groups):  # noqa
    add_member(groups["team-sre"], users["gary@a.co"], role="owner")
    add_member(groups["team-sre"], users["zay@a.co"])

    add_member(groups["tech-ops"], users["zay@a.co"], role="owner")
    add_member(groups["tech-ops"], users["gary@a.co"])

    add_member(groups["team-infra"], users["gary@a.co"], role="owner")
    add_member(groups["team-infra"], groups["team-sre"])
    add_member(groups["team-infra"], groups["tech-ops"])

    add_member(groups["all-teams"], users["testuser@a.co"], role="owner")
    add_member(groups["all-teams"], groups["team-infra"])


def test_graph_desc_to_ances(session, graph, users, groups):  # noqa
    """ Test adding members where all descendants already exist."""

    setup_desc_to_ances(session, users, groups)
    session.commit()
    graph.update_from_db(session)

    assert get_users(graph, "team-sre") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "tech-ops") == set(["gary@a.co", "zay@a.co"])

    assert get_users(graph, "team-infra") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "team-infra", cutoff=1) == set(["gary@a.co"])

    assert get_users(graph, "all-teams") == set(["gary@a.co", "zay@a.co", "testuser@a.co"])
    assert get_users(graph, "all-teams", cutoff=1) == set(["testuser@a.co"])

    assert get_groups(graph, "gary@a.co") == set(["team-sre", "all-teams", "tech-ops",
            "team-infra"])
    assert get_groups(graph, "gary@a.co", cutoff=1) == set(["team-sre", "tech-ops", "team-infra"])

    assert get_groups(graph, "zay@a.co") == set(["team-sre", "all-teams", "tech-ops", "team-infra"])
    assert get_groups(graph, "zay@a.co", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "testuser@a.co") == set(["all-teams"])
    assert get_groups(graph, "testuser@a.co", cutoff=1) == set(["all-teams"])


def test_graph_add_member_existing(session, graph, users, groups):  # noqa
    """ Test adding members to an existing relationship."""

    add_member(groups["team-sre"], users["gary@a.co"], role="owner")
    add_member(groups["tech-ops"], users["gary@a.co"], role="owner")

    add_member(groups["team-infra"], users["gary@a.co"], role="owner")
    add_member(groups["team-infra"], groups["team-sre"])
    add_member(groups["team-infra"], groups["tech-ops"])

    add_member(groups["all-teams"], users["testuser@a.co"], role="owner")
    add_member(groups["all-teams"], groups["team-infra"])

    add_member(groups["team-sre"], users["zay@a.co"])
    add_member(groups["tech-ops"], users["zay@a.co"])

    session.commit()
    graph.update_from_db(session)

    assert get_users(graph, "team-sre") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "tech-ops") == set(["gary@a.co", "zay@a.co"])

    assert get_users(graph, "team-infra") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "team-infra", cutoff=1) == set(["gary@a.co"])

    assert get_users(graph, "all-teams") == set(["gary@a.co", "zay@a.co", "testuser@a.co"])
    assert get_users(graph, "all-teams", cutoff=1) == set(["testuser@a.co"])

    assert get_groups(graph, "gary@a.co") == set(["team-sre", "all-teams", "tech-ops",
            "team-infra"])
    assert get_groups(graph, "gary@a.co", cutoff=1) == set(["team-sre", "tech-ops", "team-infra"])

    assert get_groups(graph, "zay@a.co") == set(["team-sre", "all-teams", "tech-ops", "team-infra"])
    assert get_groups(graph, "zay@a.co", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "testuser@a.co") == set(["all-teams"])
    assert get_groups(graph, "testuser@a.co", cutoff=1) == set(["all-teams"])


def test_graph_with_removes(session, graph, users, groups):  # noqa
    """ Test adding members where all descendants already exist."""

    setup_desc_to_ances(session, users, groups)

    groups["team-infra"].revoke_member(users["gary@a.co"], users["gary@a.co"], "Unit Testing")
    session.commit()
    graph.update_from_db(session)
    assert get_users(graph, "team-sre") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "tech-ops") == set(["gary@a.co", "zay@a.co"])

    assert get_users(graph, "team-infra") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "team-infra", cutoff=1) == set()

    assert get_users(graph, "all-teams") == set(["gary@a.co", "zay@a.co", "testuser@a.co"])
    assert get_users(graph, "all-teams", cutoff=1) == set(["testuser@a.co"])

    assert get_groups(graph, "gary@a.co") == set(["team-sre", "all-teams", "tech-ops",
        "team-infra"])
    assert get_groups(graph, "gary@a.co", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "zay@a.co") == set(["team-sre", "all-teams", "tech-ops", "team-infra"])
    assert get_groups(graph, "zay@a.co", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "testuser@a.co") == set(["all-teams"])
    assert get_groups(graph, "testuser@a.co", cutoff=1) == set(["all-teams"])

    groups["all-teams"].revoke_member(users["gary@a.co"], groups["team-infra"], "Unit Testing")
    session.commit()
    graph.update_from_db(session)
    assert get_users(graph, "team-sre") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "tech-ops") == set(["gary@a.co", "zay@a.co"])

    assert get_users(graph, "team-infra") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "team-infra", cutoff=1) == set([])

    assert get_users(graph, "all-teams") == set(["testuser@a.co"])
    assert get_users(graph, "all-teams", cutoff=1) == set(["testuser@a.co"])

    assert get_groups(graph, "gary@a.co") == set(["team-sre", "tech-ops", "team-infra"])
    assert get_groups(graph, "gary@a.co", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "zay@a.co") == set(["team-sre", "tech-ops", "team-infra"])
    assert get_groups(graph, "zay@a.co", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "testuser@a.co") == set(["all-teams"])
    assert get_groups(graph, "testuser@a.co", cutoff=1) == set(["all-teams"])

    groups["team-infra"].revoke_member(users["gary@a.co"], groups["tech-ops"], "Unit Testing")
    session.commit()
    graph.update_from_db(session)
    assert get_users(graph, "team-sre") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "tech-ops") == set(["gary@a.co", "zay@a.co"])

    assert get_users(graph, "team-infra") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "team-infra", cutoff=1) == set([])

    assert get_users(graph, "all-teams") == set(["testuser@a.co"])
    assert get_users(graph, "all-teams", cutoff=1) == set(["testuser@a.co"])

    assert get_groups(graph, "gary@a.co") == set(["team-sre", "tech-ops", "team-infra"])
    assert get_groups(graph, "gary@a.co", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "zay@a.co") == set(["team-sre", "tech-ops", "team-infra"])
    assert get_groups(graph, "zay@a.co", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "testuser@a.co") == set(["all-teams"])
    assert get_groups(graph, "testuser@a.co", cutoff=1) == set(["all-teams"])


def test_graph_cycle_direct(session, graph, users, groups):  # noqa
    """ Test adding members where all descendants already exist."""

    add_member(groups["team-sre"], users["gary@a.co"])
    add_member(groups["tech-ops"], users["zay@a.co"])

    add_member(groups["team-sre"], groups["tech-ops"])
    add_member(groups["tech-ops"], groups["team-sre"])

    session.commit()
    graph.update_from_db(session)
    assert get_users(graph, "team-sre") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "team-sre", cutoff=1) == set(["gary@a.co"])

    assert get_users(graph, "tech-ops") == set(["gary@a.co", "zay@a.co"])
    assert get_users(graph, "tech-ops", cutoff=1) == set(["zay@a.co"])

    assert get_groups(graph, "gary@a.co") == set(["team-sre", "tech-ops"])
    assert get_groups(graph, "gary@a.co", cutoff=1) == set(["team-sre"])

    assert get_groups(graph, "zay@a.co") == set(["team-sre", "tech-ops"])
    assert get_groups(graph, "zay@a.co", cutoff=1) == set(["tech-ops"])


def test_graph_cycle_indirect(session, graph, users, groups):  # noqa
    """ Test adding a member that will create a cycle.

        gary         zay            testuser
         |            |                |
        sre <----- tech-ops <----- team-infra <--
         |                                       |
         |                                       |
          --------> all-teams --------------------

    """

    add_member(groups["team-sre"], users["gary@a.co"])
    add_member(groups["tech-ops"], users["zay@a.co"])
    add_member(groups["team-infra"], users["testuser@a.co"])

    add_member(groups["team-sre"], groups["tech-ops"])
    add_member(groups["tech-ops"], groups["team-infra"])
    add_member(groups["team-infra"], groups["all-teams"])

    add_member(groups["all-teams"], groups["team-sre"])

    session.commit()
    graph.update_from_db(session)
    all_users = set(["gary@a.co", "zay@a.co", "testuser@a.co"])
    all_groups = set(["team-sre", "all-teams", "tech-ops", "team-infra"])

    assert get_users(graph, "team-sre") == all_users
    assert get_users(graph, "team-sre", cutoff=1) == set(["gary@a.co"])

    assert get_users(graph, "tech-ops") == all_users
    assert get_users(graph, "tech-ops", cutoff=1) == set(["zay@a.co"])

    assert get_users(graph, "team-infra") == all_users
    assert get_users(graph, "team-infra", cutoff=1) == set(["testuser@a.co"])

    assert get_users(graph, "all-teams") == all_users
    assert get_users(graph, "all-teams", cutoff=1) == set([])

    assert get_groups(graph, "gary@a.co") == all_groups
    assert get_groups(graph, "gary@a.co", cutoff=1) == set(["team-sre"])

    assert get_groups(graph, "zay@a.co") == all_groups
    assert get_groups(graph, "zay@a.co", cutoff=1) == set(["tech-ops"])

    assert get_groups(graph, "testuser@a.co") == all_groups
    assert get_groups(graph, "testuser@a.co", cutoff=1) == set(["team-infra"])


@pytest.mark.gen_test
def test_graph_disable(session, graph, groups, http_client, base_url):  # noqa
    """ Test that disabled groups work with the graph as expected."""
    groupname = u'serving-team'

    graph.update_from_db(session)
    old_groups = graph.groups
    assert sorted(old_groups) == sorted(groups.keys())
    assert groupname in graph.permission_metadata

    # disable a group
    fe_url = url(base_url, '/groups/{}/disable'.format(groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            headers={"X-Grouper-User": "zorkian@a.co"}, body=urlencode({"name": groupname}))
    assert resp.code == 200

    graph.update_from_db(session)
    assert len(graph.groups) == (len(old_groups) - 1), 'disabled group removed from graph'
    assert groupname not in graph.groups
    assert groupname not in graph.permission_metadata


@pytest.mark.gen_test
def test_group_disable(session, groups, http_client, base_url):
    # create global audit
    fe_url = url(base_url, '/audits/create')
    ends_at = date.today() + timedelta(days=7)
    resp = yield http_client.fetch(fe_url, method="POST",
            headers={"X-Grouper-User": "zorkian@a.co"},
            body=urlencode({"ends_at": ends_at.strftime("%m/%d/%Y")}))
    assert resp.code == 200

    serving_team, just_created = Group.get_or_create(session, groupname="serving-team")
    assert not just_created
    assert serving_team.audit
    assert not serving_team.audit.complete

    # disable with insufficient permissions
    fe_url = url(base_url, '/groups/serving-team/disable')
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(fe_url, method="POST",
                headers={"X-Grouper-User": "gary@a.co"}, body=urlencode({"name": "serving-team"}))

    # disable
    fe_url = url(base_url, '/groups/serving-team/disable')
    resp = yield http_client.fetch(fe_url, method="POST",
            headers={"X-Grouper-User": "zorkian@a.co"}, body=urlencode({"name": "serving-team"}))
    assert resp.code == 200

    serving_team, just_created = Group.get_or_create(session, groupname="serving-team")
    assert not just_created
    assert serving_team.audit
    assert serving_team.audit.complete, "disabling group should complete any outstanding audit"


@pytest.mark.gen_test
def test_graph_edit_role(session, graph, standard_graph, groups, users):
    """Test that membership role changes are refected in the graph."""
    username = "figurehead@a.co"

    user_role = graph.get_group_details("tech-ops")["users"][username]["rolename"]
    assert user_role == "np-owner"

    groups["tech-ops"].edit_member(users["zorkian@a.co"], users[username], "a reason",
            role="owner")

    graph.update_from_db(session)
    user_role = graph.get_group_details("tech-ops")["users"][username]["rolename"]
    assert user_role == "owner"
