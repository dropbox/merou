from typing import TYPE_CHECKING

from grouper.entities.permission_grant import AllGrants, AllGrantsOfPermission
from grouper.usecases.list_grants import ListGrantsUI

if TYPE_CHECKING:
    from tests.setup import SetupTest
    from typing import Dict


class MockUI(ListGrantsUI):
    def __init__(self):
        # type: () -> None
        self.grants = {}  # type: AllGrants
        self.grants_of_permission = {}  # type: Dict[str, AllGrantsOfPermission]

    def listed_grants(self, grants):
        # type: (AllGrants) -> None
        self.grants = grants

    def listed_grants_of_permission(self, permission, grants):
        # type: (str, AllGrantsOfPermission) -> None
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


def test_list_grants(setup):
    # type: (SetupTest) -> None
    with setup.transaction():
        create_graph(setup)

    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_list_grants_usecase(mock_ui)
    usecase.list_grants()

    expected = {
        "not-gary": AllGrantsOfPermission(users={"zorkian@a.co": ["foo"]}, service_accounts={}),
        "other-permission": AllGrantsOfPermission(users={"gary@a.co": [""]}, service_accounts={}),
        "some-permission": AllGrantsOfPermission(
            users={"gary@a.co": ["bar", "foo"], "zorkian@a.co": ["*"]},
            service_accounts={"service@svc.localhost": ["*"]},
        ),
        "twice": AllGrantsOfPermission(users={"gary@a.co": ["*"]}, service_accounts={}),
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
        "some-permission": AllGrantsOfPermission(
            users={"gary@a.co": ["bar", "foo"], "zorkian@a.co": ["*"]},
            service_accounts={"service@svc.localhost": ["*"]},
        )
    }


def test_unknown_permission(setup):
    # type: (SetupTest) -> None
    mock_ui = MockUI()
    usecase = setup.usecase_factory.create_list_grants_usecase(mock_ui)
    usecase.list_grants_of_permission("unknown-permission")
    assert mock_ui.grants == {}
    assert mock_ui.grants_of_permission == {"unknown-permission": AllGrantsOfPermission({}, {})}
