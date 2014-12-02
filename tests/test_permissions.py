from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa

from util import grant_permission, get_group_permissions, get_user_permissions


def test_basic_permission(standard_graph, session, users, groups, permissions):
    """ Test adding some permissions to various groups and ensuring that the permissions are all
        implemented as expected. This also tests permissions inheritance in the graph. """

    graph = standard_graph  # noqa

    grant_permission(groups["team-sre"], permissions["ssh"], argument="*")
    grant_permission(groups["tech-ops"], permissions["ssh"], argument="shell")
    grant_permission(groups["team-infra"], permissions["sudo"], argument="shell")

    session.commit()
    graph.update_from_db(session)

    assert sorted(get_group_permissions(graph, "team-sre")) == ["ssh:*", "sudo:shell"]
    assert sorted(get_group_permissions(graph, "tech-ops")) == ["ssh:shell", "sudo:shell"]
    assert sorted(get_group_permissions(graph, "team-infra")) == ["sudo:shell"]
    assert sorted(get_group_permissions(graph, "all-teams")) == []

    assert sorted(get_user_permissions(graph, "gary")) == ["ssh:*", "ssh:shell", "sudo:shell"]
    assert sorted(get_user_permissions(graph, "zay")) == ["ssh:*", "ssh:shell", "sudo:shell"]
    assert sorted(get_user_permissions(graph, "zorkian")) == ["ssh:*", "sudo:shell"]
    assert sorted(get_user_permissions(graph, "testuser")) == []
