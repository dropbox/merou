from typing import TYPE_CHECKING
from urllib.parse import urlencode

import pytest
from tornado.httpclient import HTTPError

from grouper.constants import USER_ADMIN
from grouper.group_service_account import get_service_accounts
from grouper.models.group import Group
from grouper.models.user import User
from grouper.plugin import get_plugin_proxy
from grouper.plugin.base import BasePlugin
from grouper.plugin.exceptions import PluginRejectedMachineSet
from grouper.service_account import (
    can_manage_service_account,
    disable_service_account,
    enable_service_account,
)
from tests.fixtures import (  # noqa: F401
    fe_app as app,
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)
from tests.url_util import url

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_service_accounts(setup):
    # type: (SetupTest) -> None
    """Tests remaining non-usecase service account functions."""
    with setup.transaction():
        setup.create_service_account(
            "service@a.co", "team-sre", "some machines", "some service account"
        )
        setup.add_user_to_group("zorkian@a.co", "team-sre", "owner")
        setup.add_user_to_group("zorkian@a.co", "admins")
        setup.grant_permission_to_group(USER_ADMIN, "", "admins")
        setup.add_user_to_group("gary@a.co", "team-sre")
        setup.create_user("oliver@a.co")
        setup.grant_permission_to_service_account("team-sre", "*", "service@a.co")
        setup.create_group("security-team")

    group = Group.get(setup.session, name="team-sre")
    assert group
    accounts = get_service_accounts(setup.session, group)
    assert len(accounts) == 1
    service_account = accounts[0]
    assert service_account.user.name == "service@a.co"
    assert service_account.user.is_service_account

    # zorkian should be able to manage the account, as should gary, but oliver (not a member of the
    # group) should not.
    zorkian_user = User.get(setup.session, name="zorkian@a.co")
    assert zorkian_user
    gary_user = User.get(setup.session, name="gary@a.co")
    assert gary_user
    oliver_user = User.get(setup.session, name="oliver@a.co")
    assert oliver_user
    assert can_manage_service_account(setup.session, service_account, zorkian_user)
    assert can_manage_service_account(setup.session, service_account, gary_user)
    assert not can_manage_service_account(setup.session, service_account, oliver_user)

    # Diabling the service account should remove the link to the group.
    disable_service_account(setup.session, zorkian_user, service_account)
    assert service_account.user.enabled == False
    assert get_service_accounts(setup.session, group) == []

    # The user should also be gone from the graph and have its permissions removed.
    setup.graph.update_from_db(setup.session)
    group_details = setup.graph.get_group_details("team-sre")
    assert "service_accounts" not in group_details
    metadata = setup.graph.user_metadata["service@a.co"]
    assert not metadata["enabled"]
    assert "owner" not in metadata["service_account"]
    user_details = setup.graph.get_user_details("service@a.co")
    assert user_details["permissions"] == []

    # We can re-enable and attach to a different group.
    new_group = Group.get(setup.session, name="security-team")
    assert new_group
    enable_service_account(setup.session, zorkian_user, service_account, new_group)
    assert service_account.user.enabled == True
    assert get_service_accounts(setup.session, group) == []
    accounts = get_service_accounts(setup.session, new_group)
    assert len(accounts) == 1
    assert accounts[0].user.name == "service@a.co"

    # Check that this is reflected in the graph and the user has no permissions.
    setup.graph.update_from_db(setup.session)
    group_details = setup.graph.get_group_details("security-team")
    assert group_details["service_accounts"] == ["service@a.co"]
    metadata = setup.graph.user_metadata["service@a.co"]
    assert metadata["service_account"]["owner"] == "security-team"
    user_details = setup.graph.get_user_details("service@a.co")
    assert user_details["permissions"] == []


@pytest.mark.gen_test
def test_service_account_fe_disable(
    session, standard_graph, graph, http_client, base_url  # noqa: F811
):
    admin = "tyleromeara@a.co"
    owner = "gary@a.co"
    plebe = "oliver@a.co"

    # Unrelated people cannot disable the service account.
    fe_url = url(base_url, "/groups/security-team/service/service@a.co/disable")
    with pytest.raises(HTTPError):
        yield http_client.fetch(
            fe_url, method="POST", headers={"X-Grouper-User": plebe}, body=urlencode({})
        )

    # Group members can disable the service account.
    resp = yield http_client.fetch(
        fe_url, method="POST", headers={"X-Grouper-User": owner}, body=urlencode({})
    )
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert not metadata["enabled"]
    group_details = graph.get_group_details("team-sre")
    assert "service_accounts" not in group_details

    # The group owner cannot enable the account, since the group ownership has been lost
    fe_url = url(base_url, "/service/service@a.co/enable")
    with pytest.raises(HTTPError):
        yield http_client.fetch(
            fe_url,
            method="POST",
            headers={"X-Grouper-User": owner},
            body=urlencode({"owner": "team-sre"}),
        )

    # A global admin can enable the account.
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        headers={"X-Grouper-User": admin},
        body=urlencode({"owner": "team-sre"}),
    )
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["enabled"]
    assert metadata["service_account"]["owner"] == "team-sre"
    group_details = graph.get_group_details("team-sre")
    assert group_details["service_accounts"] == ["service@a.co"]

    # And can also disable the account even though they're not a member of the group.
    fe_url = url(base_url, "/groups/security-team/service/service@a.co/disable")
    resp = yield http_client.fetch(
        fe_url, method="POST", headers={"X-Grouper-User": admin}, body=urlencode({})
    )
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert not metadata["enabled"]


@pytest.mark.gen_test
def test_service_account_fe_edit(
    session, standard_graph, graph, http_client, base_url  # noqa: F811
):
    owner = "gary@a.co"
    plebe = "oliver@a.co"
    admin = "tyleromeara@a.co"

    # Unrelated people cannot edit the service account.
    fe_url = url(base_url, "/groups/team-sre/service/service@a.co/edit")
    update = {"description": "desc", "machine_set": "machines"}
    with pytest.raises(HTTPError):
        yield http_client.fetch(
            fe_url, method="POST", headers={"X-Grouper-User": plebe}, body=urlencode(update)
        )

    # A group member can.
    resp = yield http_client.fetch(
        fe_url, method="POST", headers={"X-Grouper-User": owner}, body=urlencode(update)
    )
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["service_account"]["description"] == "desc"
    assert metadata["service_account"]["machine_set"] == "machines"

    # A user admin also can.
    update["description"] = "done by admin"
    resp = yield http_client.fetch(
        fe_url, method="POST", headers={"X-Grouper-User": admin}, body=urlencode(update)
    )
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["service_account"]["description"] == "done by admin"


class MachineSetPlugin(BasePlugin):
    """Test plugin that rejects some machine sets."""

    def check_machine_set(self, name, machine_set):
        # type: (str, str) -> None
        if "okay" not in machine_set:
            raise PluginRejectedMachineSet("{} has invalid machine set".format(name))


@pytest.mark.gen_test
def test_machine_set_plugin(session, standard_graph, graph, http_client, base_url):  # noqa: F811
    get_plugin_proxy().add_plugin(MachineSetPlugin())
    admin = "zorkian@a.co"

    # Edit the metadata of an existing service account.  This should fail (although return 200)
    # including the appropriate error.
    update = {"description": "some service account", "machine_set": "not valid"}
    fe_url = url(base_url, "/groups/team-sre/service/service@a.co/edit")
    resp = yield http_client.fetch(
        fe_url, method="POST", headers={"X-Grouper-User": admin}, body=urlencode(update)
    )
    assert resp.code == 200
    assert b"service@a.co has invalid machine set" in resp.body
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["service_account"]["machine_set"] == "some machines"

    # Use a valid machine set, and then this should go through.
    update["machine_set"] = "is okay"
    resp = yield http_client.fetch(
        fe_url, method="POST", headers={"X-Grouper-User": admin}, body=urlencode(update)
    )
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["service_account"]["machine_set"] == "is okay"
