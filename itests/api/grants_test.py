from typing import TYPE_CHECKING

from groupy.client import Groupy

from itests.setup import api_server

if TYPE_CHECKING:
    from py.path import LocalPath
    from tests.setup import SetupTest


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


def test_list_grants(tmpdir, setup):
    # type: (LocalPath, SetupTest) -> None
    with setup.transaction():
        create_graph(setup)

    expected = {
        "not-gary": {"users": {"zorkian@a.co": ["foo"]}, "service_accounts": {}},
        "other-permission": {"users": {"gary@a.co": [""]}, "service_accounts": {}},
        "some-permission": {
            "users": {"gary@a.co": ["bar", "foo"], "zorkian@a.co": ["*"]},
            "service_accounts": {"service@svc.localhost": ["*"]},
        },
        "twice": {"users": {"gary@a.co": ["*"]}, "service_accounts": {}},
    }

    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        result = api_client._fetch("/grants")
        assert result["status"] == "ok"
        assert result["data"]["permissions"] == expected


def test_list_grants_of_permission(tmpdir, setup):
    # type: (LocalPath, SetupTest) -> None
    with setup.transaction():
        create_graph(setup)

    expected = {
        "users": {"gary@a.co": ["bar", "foo"], "zorkian@a.co": ["*"]},
        "service_accounts": {"service@svc.localhost": ["*"]},
    }

    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        result = api_client._fetch("/grants/some-permission")
        assert result["status"] == "ok"
        assert result["data"]["permission"] == "some-permission"
        assert result["data"]["grants"] == expected
