from fixtures import users, graph, groups, session, permissions  # noqa

from util import get_users, get_groups, add_member


def setup_desc_to_ances(session, users, groups):
    add_member(groups["team-sre"], users["gary"], role="owner")
    add_member(groups["team-sre"], users["zay"])

    add_member(groups["tech-ops"], users["zay"], role="owner")
    add_member(groups["tech-ops"], users["gary"])

    add_member(groups["team-infra"], users["gary"], role="owner")
    add_member(groups["team-infra"], groups["team-sre"])
    add_member(groups["team-infra"], groups["tech-ops"])

    add_member(groups["all-teams"], users["testuser"], role="owner")
    add_member(groups["all-teams"], groups["team-infra"])


def test_graph_desc_to_ances(session, graph, users, groups):
    """ Test adding members where all descendants already exist."""

    setup_desc_to_ances(session, users, groups)
    session.commit()
    graph.update_from_db(session)

    assert get_users(graph, "team-sre") == set(["gary", "zay"])
    assert get_users(graph, "tech-ops") == set(["gary", "zay"])

    assert get_users(graph, "team-infra") == set(["gary", "zay"])
    assert get_users(graph, "team-infra", cutoff=1) == set(["gary"])

    assert get_users(graph, "all-teams") == set(["gary", "zay", "testuser"])
    assert get_users(graph, "all-teams", cutoff=1) == set(["testuser"])

    assert get_groups(graph, "gary") == set(["team-sre", "all-teams", "tech-ops", "team-infra"])
    assert get_groups(graph, "gary", cutoff=1) == set(["team-sre", "tech-ops", "team-infra"])

    assert get_groups(graph, "zay") == set(["team-sre", "all-teams", "tech-ops", "team-infra"])
    assert get_groups(graph, "zay", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "testuser") == set(["all-teams"])
    assert get_groups(graph, "testuser", cutoff=1) == set(["all-teams"])


def test_graph_add_member_existing(session, graph, users, groups):
    """ Test adding members to an existing relationship."""

    add_member(groups["team-sre"], users["gary"], role="owner")
    add_member(groups["tech-ops"], users["gary"], role="owner")

    add_member(groups["team-infra"], users["gary"], role="owner")
    add_member(groups["team-infra"], groups["team-sre"])
    add_member(groups["team-infra"], groups["tech-ops"])

    add_member(groups["all-teams"], users["testuser"], role="owner")
    add_member(groups["all-teams"], groups["team-infra"])

    add_member(groups["team-sre"], users["zay"])
    add_member(groups["tech-ops"], users["zay"])

    session.commit()
    graph.update_from_db(session)

    assert get_users(graph, "team-sre") == set(["gary", "zay"])
    assert get_users(graph, "tech-ops") == set(["gary", "zay"])

    assert get_users(graph, "team-infra") == set(["gary", "zay"])
    assert get_users(graph, "team-infra", cutoff=1) == set(["gary"])

    assert get_users(graph, "all-teams") == set(["gary", "zay", "testuser"])
    assert get_users(graph, "all-teams", cutoff=1) == set(["testuser"])

    assert get_groups(graph, "gary") == set(["team-sre", "all-teams", "tech-ops", "team-infra"])
    assert get_groups(graph, "gary", cutoff=1) == set(["team-sre", "tech-ops", "team-infra"])

    assert get_groups(graph, "zay") == set(["team-sre", "all-teams", "tech-ops", "team-infra"])
    assert get_groups(graph, "zay", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "testuser") == set(["all-teams"])
    assert get_groups(graph, "testuser", cutoff=1) == set(["all-teams"])


def test_graph_with_removes(session, graph, users, groups):
    """ Test adding members where all descendants already exist."""

    setup_desc_to_ances(session, users, groups)

    groups["team-infra"].revoke_member(users["gary"], users["gary"], "Unit Testing")
    session.commit()
    graph.update_from_db(session)
    assert get_users(graph, "team-sre") == set(["gary", "zay"])
    assert get_users(graph, "tech-ops") == set(["gary", "zay"])

    assert get_users(graph, "team-infra") == set(["gary", "zay"])
    assert get_users(graph, "team-infra", cutoff=1) == set()

    assert get_users(graph, "all-teams") == set(["gary", "zay", "testuser"])
    assert get_users(graph, "all-teams", cutoff=1) == set(["testuser"])

    assert get_groups(graph, "gary") == set(["team-sre", "all-teams", "tech-ops", "team-infra"])
    assert get_groups(graph, "gary", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "zay") == set(["team-sre", "all-teams", "tech-ops", "team-infra"])
    assert get_groups(graph, "zay", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "testuser") == set(["all-teams"])
    assert get_groups(graph, "testuser", cutoff=1) == set(["all-teams"])

    groups["all-teams"].revoke_member(users["gary"], groups["team-infra"], "Unit Testing")
    session.commit()
    graph.update_from_db(session)
    assert get_users(graph, "team-sre") == set(["gary", "zay"])
    assert get_users(graph, "tech-ops") == set(["gary", "zay"])

    assert get_users(graph, "team-infra") == set(["gary", "zay"])
    assert get_users(graph, "team-infra", cutoff=1) == set([])

    assert get_users(graph, "all-teams") == set(["testuser"])
    assert get_users(graph, "all-teams", cutoff=1) == set(["testuser"])

    assert get_groups(graph, "gary") == set(["team-sre", "tech-ops", "team-infra"])
    assert get_groups(graph, "gary", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "zay") == set(["team-sre", "tech-ops", "team-infra"])
    assert get_groups(graph, "zay", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "testuser") == set(["all-teams"])
    assert get_groups(graph, "testuser", cutoff=1) == set(["all-teams"])

    groups["team-infra"].revoke_member(users["gary"], groups["tech-ops"], "Unit Testing")
    session.commit()
    graph.update_from_db(session)
    assert get_users(graph, "team-sre") == set(["gary", "zay"])
    assert get_users(graph, "tech-ops") == set(["gary", "zay"])

    assert get_users(graph, "team-infra") == set(["gary", "zay"])
    assert get_users(graph, "team-infra", cutoff=1) == set([])

    assert get_users(graph, "all-teams") == set(["testuser"])
    assert get_users(graph, "all-teams", cutoff=1) == set(["testuser"])

    assert get_groups(graph, "gary") == set(["team-sre", "tech-ops", "team-infra"])
    assert get_groups(graph, "gary", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "zay") == set(["team-sre", "tech-ops", "team-infra"])
    assert get_groups(graph, "zay", cutoff=1) == set(["team-sre", "tech-ops"])

    assert get_groups(graph, "testuser") == set(["all-teams"])
    assert get_groups(graph, "testuser", cutoff=1) == set(["all-teams"])


def test_graph_cycle_direct(session, graph, users, groups):
    """ Test adding members where all descendants already exist."""

    add_member(groups["team-sre"], users["gary"])
    add_member(groups["tech-ops"], users["zay"])

    add_member(groups["team-sre"], groups["tech-ops"])
    add_member(groups["tech-ops"], groups["team-sre"])

    session.commit()
    graph.update_from_db(session)
    assert get_users(graph, "team-sre") == set(["gary", "zay"])
    assert get_users(graph, "team-sre", cutoff=1) == set(["gary"])

    assert get_users(graph, "tech-ops") == set(["gary", "zay"])
    assert get_users(graph, "tech-ops", cutoff=1) == set(["zay"])

    assert get_groups(graph, "gary") == set(["team-sre", "tech-ops"])
    assert get_groups(graph, "gary", cutoff=1) == set(["team-sre"])

    assert get_groups(graph, "zay") == set(["team-sre", "tech-ops"])
    assert get_groups(graph, "zay", cutoff=1) == set(["tech-ops"])


def test_graph_cycle_indirect(session, graph, users, groups):
    """ Test adding a member that will create a cycle.

        gary         zay            testuser
         |            |                |
        sre <----- tech-ops <----- team-infra <--
         |                                       |
         |                                       |
          --------> all-teams --------------------

    """

    add_member(groups["team-sre"], users["gary"])
    add_member(groups["tech-ops"], users["zay"])
    add_member(groups["team-infra"], users["testuser"])

    add_member(groups["team-sre"], groups["tech-ops"])
    add_member(groups["tech-ops"], groups["team-infra"])
    add_member(groups["team-infra"], groups["all-teams"])

    add_member(groups["all-teams"], groups["team-sre"])

    session.commit()
    graph.update_from_db(session)
    all_users = set(["gary", "zay", "testuser"])
    all_groups = set(["team-sre", "all-teams", "tech-ops", "team-infra"])

    assert get_users(graph, "team-sre") == all_users
    assert get_users(graph, "team-sre", cutoff=1) == set(["gary"])

    assert get_users(graph, "tech-ops") == all_users
    assert get_users(graph, "tech-ops", cutoff=1) == set(["zay"])

    assert get_users(graph, "team-infra") == all_users
    assert get_users(graph, "team-infra", cutoff=1) == set(["testuser"])

    assert get_users(graph, "all-teams") == all_users
    assert get_users(graph, "all-teams", cutoff=1) == set([])

    assert get_groups(graph, "gary") == all_groups
    assert get_groups(graph, "gary", cutoff=1) == set(["team-sre"])

    assert get_groups(graph, "zay") == all_groups
    assert get_groups(graph, "zay", cutoff=1) == set(["tech-ops"])

    assert get_groups(graph, "testuser") == all_groups
    assert get_groups(graph, "testuser", cutoff=1) == set(["team-infra"])
