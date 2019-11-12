from __future__ import annotations

from typing import TYPE_CHECKING

from groupy.client import Groupy

from itests.setup import api_server

if TYPE_CHECKING:
    from py.local import LocalPath
    from tests.setup import SetupTest


def test_get_service_accounts(tmpdir: LocalPath, setup: SetupTest) -> None:
    with setup.transaction():
        setup.create_user("gary@a.co")
        setup.create_role_user("role@a.co")
        setup.create_service_account("service@a.co", "team-sre")

    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        assert sorted(api_client.service_accounts) == ["role@a.co", "service@a.co"]


def test_get_service_account(tmpdir: LocalPath, setup: SetupTest) -> None:
    with setup.transaction():
        setup.create_service_account(
            "service@a.co",
            owner="team-sre",
            machine_set="some machines",
            description="some service account",
        )

    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        service_account = api_client.service_accounts.get("service@a.co")
        assert service_account.groups == {}
        assert service_account.passwords == []
        assert service_account.public_keys == []
        assert service_account.enabled
        assert service_account.service_account == {
            "description": "some service account",
            "machine_set": "some machines",
            "owner": "team-sre",
        }
        assert service_account.permissions == []
        assert service_account.metadata == {}


def test_get_role_user(tmpdir: LocalPath, setup: SetupTest) -> None:
    with setup.transaction():
        setup.create_role_user("role@a.co")

    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        role_user = api_client.service_accounts.get("role@a.co")
        assert sorted(role_user.groups) == ["role@a.co"]
        assert role_user.passwords == []
        assert role_user.public_keys == []
        assert role_user.enabled
        assert role_user.service_account is None
        assert role_user.permissions == []
        assert role_user.metadata == {}


def test_includes_disabled_service_accounts(tmpdir: LocalPath, setup: SetupTest) -> None:
    with setup.transaction():
        setup.create_service_account("service@a.co", "some-group", "some machines", "an account")
        setup.disable_service_account("service@a.co")

    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        assert list(api_client.service_accounts) == ["service@a.co"]

        service_account = api_client.service_accounts.get("service@a.co")
        assert service_account.groups == {}
        assert not service_account.enabled
        assert service_account.service_account == {
            "description": "an account",
            "machine_set": "some machines",
        }
        assert service_account.permissions == []
