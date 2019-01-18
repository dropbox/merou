from fixtures import graph, groups, service_accounts, permissions, session, standard_graph, users  # noqa

from grouper.permissions import disable_permission, get_groups_by_permission, get_permission
from grouper.models.group import Group
from grouper.models.group_edge import GROUP_EDGE_ROLES


def test_group_edge_roles_order_unchanged():
    # The order of the GROUP_EDGE_ROLES tuple matters:  new roles must be
    # appended.  This test attempts exposes that information to help prevent
    # that from happening accidentally.
    assert GROUP_EDGE_ROLES.index("member") == 0
    assert GROUP_EDGE_ROLES.index("manager") == 1
    assert GROUP_EDGE_ROLES.index("owner") == 2
    assert GROUP_EDGE_ROLES.index("np-owner") == 3


def test_permission_exclude_inactive_groups(session, standard_graph):
    """Ensure disabled groups are excluded from permission data."""
    group = Group.get(session, name="team-sre")
    permission = get_permission(session, "ssh")
    assert "team-sre" in [g[0] for g in get_groups_by_permission(session, permission)]
    group.disable()
    assert "team-sre" not in [g[0] for g in get_groups_by_permission(session, permission)]
