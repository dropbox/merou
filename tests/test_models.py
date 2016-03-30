from fixtures import (
    graph,
    groups,
    permissions,
    session,
    standard_graph,
    users,
)  # noqa

from grouper.model_soup import GROUP_EDGE_ROLES, Group, Permission


def test_group_edge_roles_order_unchanged():
    # The order of the GROUP_EDGE_ROLES tuple matters:  new roles must be
    # appended.  This test attempts exposes that information to help prevent
    # that from happening accidentally.
    assert GROUP_EDGE_ROLES.index("member") == 0
    assert GROUP_EDGE_ROLES.index("manager") == 1
    assert GROUP_EDGE_ROLES.index("owner") == 2
    assert GROUP_EDGE_ROLES.index("np-owner") == 3


def test_permission_exclude_inactive(session, standard_graph):
    """Ensure disabled groups are excluded from permission data."""
    group = Group.get(session, name="team-sre")
    permission = Permission.get(session, "ssh")
    assert "team-sre" in [g[0] for g in permission.get_mapped_groups()]
    group.disable()
    assert "team-sre" not in [g[0] for g in permission.get_mapped_groups()]
