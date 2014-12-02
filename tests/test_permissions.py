from fixtures import *  # noqa

from util import add_member, grant_permission, get_group_permissions, get_user_permissions


def setup_standard_groups(users, groups):
    add_member(groups["team-sre"], users["gary"], role="owner")
    add_member(groups["team-sre"], users["zay"])
    add_member(groups["team-sre"], users["zorkian"])

    add_member(groups["tech-ops"], users["zay"], role="owner")
    add_member(groups["tech-ops"], users["gary"])

    add_member(groups["team-infra"], users["gary"], role="owner")
    add_member(groups["team-infra"], groups["team-sre"])
    add_member(groups["team-infra"], groups["tech-ops"])

    add_member(groups["all-teams"], users["testuser"], role="owner")
    add_member(groups["all-teams"], groups["team-infra"])


def test_basic_permission(session, graph, users, groups, permissions):
    """ Test adding some permissions to various groups and ensuring that the permissions are all
        implemented as expected. This also tests permissions inheritance in the graph. """

    setup_standard_groups(users, groups)

    grant_permission(groups["team-sre"], permissions["ssh"], argument="*")
    grant_permission(groups["tech-ops"], permissions["ssh"], argument="shell")
    grant_permission(groups["team-infra"], permissions["sudo"], argument="shell")

    session.commit()
    graph.update_from_db(session)

    assert get_group_permissions(graph, "team-sre") == set(["ssh:*", "sudo:shell"])
    assert get_group_permissions(graph, "tech-ops") == set(["ssh:shell", "sudo:shell"])
    assert get_group_permissions(graph, "team-infra") == set(["sudo:shell"])
    assert get_group_permissions(graph, "all-teams") == set()

    assert get_user_permissions(graph, "gary") == set(["ssh:*", "ssh:shell", "sudo:shell"])
    assert get_user_permissions(graph, "zay") == set(["ssh:*", "ssh:shell", "sudo:shell"])
    assert get_user_permissions(graph, "zorkian") == set(["ssh:*", "sudo:shell"])
    assert get_user_permissions(graph, "testuser") == set()
