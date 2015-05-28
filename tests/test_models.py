from grouper.models import GROUP_EDGE_ROLES

def test_group_edge_roles_order_unchanged():
    # The order of the GROUP_EDGE_ROLES tuple matters:  new roles must be
    # appended.  This test attempts exposes that information to help prevent
    # that from happening accidentally.
    assert GROUP_EDGE_ROLES.index("member") == 0
    assert GROUP_EDGE_ROLES.index("manager") == 1
    assert GROUP_EDGE_ROLES.index("owner") == 2
    assert GROUP_EDGE_ROLES.index("np-owner") == 3
