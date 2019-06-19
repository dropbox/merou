from typing import TYPE_CHECKING

from grouper.entities.permission_grant import UniqueGrantsOfPermission
from grouper.usecases.list_grants import ListGrantsUI

if TYPE_CHECKING:
    from tests.setup import SetupTest
    from typing import Dict


class MockUI(ListGrantsUI):
    def __init__(self):
        # type: () -> None
        self.grants = {}  # type: Dict[str, UniqueGrantsOfPermission]
        self.grants_of_permission = {}  # type: Dict[str, UniqueGrantsOfPermission]

    def listed_grants(self, grants):
        # type: (Dict[str, UniqueGrantsOfPermission]) -> None
        self.grants = grants

    def listed_grants_of_permission(self, permission, grants):
        # type: (str, UniqueGrantsOfPermission) -> None
        self.grants_of_permission[permission] = grants


def create_graph(setup):
    # type: (SetupTest) -> None
    """Create a simple graph structure with some permission grants."""
    setup.add_user_to_group("gary@a.co", "some-group")
    setup.grant_permission_to_group("some-permission", "foo", "some-group")
    setup.add_user_to_group("gary@a.co", "other-group")
    setup.grant_permission_to_group("other-permission", "", "other-group")
    setup.grant_permission_to_group("not-gary", "foo", "not-member-group")
    setup.grant_permission_to_group("some-permission", "*", "not-member-group")
    setup.grant_permission_to_group("some-permission", "bar", "parent-group")
    setup.add_group_to_group("some-group", "parent-group")
    setup.grant_permission_to_group("twice", "*", "group-one")
    setup.grant_permission_to_group("twice", "*", "group-two")
    setup.add_group_to_group("child-group", "group-one")
    setup.add_group_to_group("child-group", "group-two")
    setup.add_user_to_group("gary@a.co", "child-group")
    setup.add_user_to_group("zorkian@a.co", "not-member-group")
    setup.create_user("oliver@a.co")
    setup.create_service_account("service@svc.localhost", "some-group")
    setup.grant_permission_to_service_account("some-permission", "*", "service@svc.localhost")
    setup.create_role_user("role-user@a.co")
    setup.grant_permission_to_group("some-permission", "foo", "role-user@a.co")
    setup.grant_permission_to_group("some-permission", "role", "role-user@a.co")


def test_list_grants(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        create_graph(setup)

    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_list_grants_usecase(mock_ui)
    usecase.list_grants()

    expected = {
        "not-gary": UniqueGrantsOfPermission(
            users={"zorkian@a.co": ["foo"]}, role_users={}, service_accounts={}
        ),
        "other-permission": UniqueGrantsOfPermission(
            users={"gary@a.co": [""]}, role_users={}, service_accounts={}
        ),
        "some-permission": UniqueGrantsOfPermission(
            users={"gary@a.co": ["bar", "foo"], "zorkian@a.co": ["*"]},
            role_users={"role-user@a.co": ["foo", "role"]},
            service_accounts={"service@svc.localhost": ["*"]},
        ),
        "twice": UniqueGrantsOfPermission(
            users={"gary@a.co": ["*"]}, role_users={}, service_accounts={}
        ),
    }
    assert mock_ui.grants == expected
    assert mock_ui.grants_of_permission == {}


def test_list_grants_of_permission(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        create_graph(setup)

    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_list_grants_usecase(mock_ui)
    usecase.list_grants_of_permission("some-permission")
    assert mock_ui.grants == {}
    assert mock_ui.grants_of_permission == {
        "some-permission": UniqueGrantsOfPermission(
            users={"gary@a.co": ["bar", "foo"], "zorkian@a.co": ["*"]},
            role_users={"role-user@a.co": ["foo", "role"]},
            service_accounts={"service@svc.localhost": ["*"]},
        )
    }


def test_unknown_permission(setup):
    # type: (SetupTest) -> None
    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_list_grants_usecase(mock_ui)
    usecase.list_grants_of_permission("unknown-permission")
    assert mock_ui.grants == {}
    assert mock_ui.grants_of_permission == {
        "unknown-permission": UniqueGrantsOfPermission(
            users={}, role_users={}, service_accounts={}
        )
    }


def test_np_owner_grants(setup):
    # type: (SetupTest) -> None
    """Test special behavior of np-owner.

    np-owner roles should not cause permission grants to pass on to the user with that role, either
    as a direct member or as np-owner of a group that in turn is a member of the group with the
    permission.  To make things even trickier, the user who is an np-owner on the shortest path
    should still get the permission if there is some other path that doesn't involve np-owner.
    This sets up a graph to test this behavior.
    """
    with setup.transaction():
        setup.add_user_to_group("user@a.co", "group")
        setup.add_user_to_group("user@a.co", "np-group", "np-owner")
        setup.grant_permission_to_group("permission", "direct", "np-group")
        setup.add_group_to_group("np-group", "parent-group")
        setup.grant_permission_to_group("permission", "parent", "parent-group")
        setup.add_group_to_group("group", "intermediate-group")
        setup.add_group_to_group("intermediate-group", "grandparent-group")
        setup.add_group_to_group("np-group", "grandparent-group")
        setup.grant_permission_to_group("permission", "grandparent", "grandparent-group")

    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_list_grants_usecase(mock_ui)
    usecase.list_grants()
    assert mock_ui.grants == {
        "permission": UniqueGrantsOfPermission(
            users={"user@a.co": ["grandparent"]}, role_users={}, service_accounts={}
        )
    }


def test_broken_service_account_grants(setup):
    # type: (SetupTest) -> None
    """Test correct handling of a bug in service account membership.

    It's currently possible to add the user underlying a service account directly to a group.  This
    was not intended behavior, but unfortunately some code depends on this behavior, so we can't
    fix it (yet).  Until then, we want to suppress any permissions derived from such membership
    from the graph underlying /grants to maintain separation between service account permissions
    and user permissions.  This tests that we do so correctly.

    TODO(rra): Remove this test once we've cleaned up service account membership handling.
    """
    with setup.transaction():
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.grant_permission_to_service_account("service", "bar", "service@svc.localhost")
        setup.grant_permission_to_group("some-permission", "foo", "another-group")
        setup.add_user_to_group("service@svc.localhost", "another-group")

    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_list_grants_usecase(mock_ui)
    usecase.list_grants()
    assert mock_ui.grants == {
        "service": UniqueGrantsOfPermission(
            users={}, role_users={}, service_accounts={"service@svc.localhost": ["bar"]}
        )
    }
