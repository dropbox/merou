from urllib import urlencode

import pytest
from tornado.httpclient import HTTPError

from fixtures import fe_app as app  # noqa: F401
from fixtures import graph, groups, permissions, session, standard_graph, users  # noqa: F401
from grouper.group_service_account import get_service_accounts
from grouper.models.service_account import ServiceAccount
from grouper.permissions import grant_permission_to_service_account
from grouper.plugin.base import BasePlugin
from grouper.plugin.exceptions import PluginRejectedMachineSet
from grouper.plugin.proxy import PluginProxy
from grouper.service_account import (
    can_manage_service_account,
    create_service_account,
    disable_service_account,
    DuplicateServiceAccount,
    enable_service_account,
    is_service_account,
    service_account_permissions,
)
from url_util import url


def test_service_accounts(session, standard_graph, users, groups, permissions):
    graph = standard_graph

    # Create a service account.
    service_account = ServiceAccount.get(session, name="service@a.co")
    assert service_account.description == "some service account"
    assert service_account.machine_set == "some machines"
    assert service_account.user.name == "service@a.co"
    assert service_account.user.enabled == True
    assert service_account.user.is_service_account == True
    service_accounts = get_service_accounts(session, groups["team-sre"])
    assert len(service_accounts) == 1
    assert service_accounts[0].user.name == "service@a.co"
    assert is_service_account(session, service_account.user)

    # Duplicates should raise an exception.
    with pytest.raises(DuplicateServiceAccount):
        create_service_account(
            session, users["zay@a.co"], "service@a.co", "dup", "dup", groups["team-sre"])

    # zorkian should be able to manage the account, as should gary, but oliver (not a member of the
    # group) should not.
    assert can_manage_service_account(session, service_account, users["zorkian@a.co"])
    assert can_manage_service_account(session, service_account, users["gary@a.co"])
    assert not can_manage_service_account(session, service_account, users["oliver@a.co"])

    # Check that the user appears in the graph.
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["enabled"]
    assert metadata["service_account"]["description"] == "some service account"
    assert metadata["service_account"]["machine_set"] == "some machines"
    assert metadata["service_account"]["owner"] == "team-sre"
    group_details = graph.get_group_details("team-sre")
    assert group_details["service_accounts"] == ["service@a.co"]

    # Grant a permission to the service account and check it in the graph.
    grant_permission_to_service_account(session, service_account, permissions["team-sre"], "*")
    graph.update_from_db(session)
    user_details = graph.get_user_details("service@a.co")
    assert user_details["permissions"][0]["permission"] == "team-sre"
    assert user_details["permissions"][0]["argument"] == "*"

    # Diabling the service account should remove the link to the group.
    disable_service_account(session, users["zorkian@a.co"], service_account)
    assert service_account.user.enabled == False
    assert get_service_accounts(session, groups["team-sre"]) == []

    # The user should also be gone from the graph and have its permissions removed.
    graph.update_from_db(session)
    group_details = graph.get_group_details("team-sre")
    assert "service_accounts" not in group_details
    metadata = graph.user_metadata["service@a.co"]
    assert not metadata["enabled"]
    assert "owner" not in metadata["service_account"]
    user_details = graph.get_user_details("service@a.co")
    assert user_details["permissions"] == []

    # We can re-enable and attach to a different group.
    new_group = groups["security-team"]
    enable_service_account(session, users["zorkian@a.co"], service_account, new_group)
    assert service_account.user.enabled == True
    assert get_service_accounts(session, groups["team-sre"]) == []
    service_accounts = get_service_accounts(session, new_group)
    assert len(service_accounts) == 1
    assert service_accounts[0].user.name == "service@a.co"

    # Check that this is reflected in the graph and the user has no permissions.
    graph.update_from_db(session)
    group_details = graph.get_group_details("security-team")
    assert group_details["service_accounts"] == ["service@a.co"]
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["service_account"]["owner"] == "security-team"
    user_details = graph.get_user_details("service@a.co")
    assert user_details["permissions"] == []


@pytest.mark.gen_test
def test_service_account_fe_disable(session, standard_graph, http_client, base_url):
    graph = standard_graph
    admin = "tyleromeara@a.co"
    owner = "gary@a.co"
    plebe = "oliver@a.co"

    # Unrelated people cannot disable the service account.
    fe_url = url(base_url, "/groups/security-team/service/service@a.co/disable")
    with pytest.raises(HTTPError):
        yield http_client.fetch(fe_url, method="POST",
                headers={"X-Grouper-User": plebe}, body=urlencode({}))

    # Group members can disable the service account.
    resp = yield http_client.fetch(fe_url, method="POST",
            headers={"X-Grouper-User": owner}, body=urlencode({}))
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert not metadata["enabled"]
    group_details = graph.get_group_details("team-sre")
    assert "service_accounts" not in group_details

    # The group owner cannot enable the account, since the group ownership has been lost
    fe_url = url(base_url, "/service/service@a.co/enable")
    with pytest.raises(HTTPError):
        yield http_client.fetch(fe_url, method="POST",
                headers={"X-Grouper-User": owner}, body=urlencode({"owner": "team-sre"}))

    # A global admin can enable the account.
    resp = yield http_client.fetch(fe_url, method="POST",
            headers={"X-Grouper-User": admin}, body=urlencode({"owner": "team-sre"}))
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["enabled"]
    assert metadata["service_account"]["owner"] == "team-sre"
    group_details = graph.get_group_details("team-sre")
    assert group_details["service_accounts"] == ["service@a.co"]

    # And can also disable the account even though they're not a member of the group.
    fe_url = url(base_url, "/groups/security-team/service/service@a.co/disable")
    resp = yield http_client.fetch(fe_url, method="POST",
            headers={"X-Grouper-User": admin}, body=urlencode({}))
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert not metadata["enabled"]


@pytest.mark.gen_test
def test_service_account_fe_edit(session, standard_graph, http_client, base_url):
    graph = standard_graph
    owner = "gary@a.co"
    plebe = "oliver@a.co"

    # Unrelated people cannot edit the service account.
    fe_url = url(base_url, "/groups/security-team/service/service@a.co/edit")
    update = {
        "description": "desc",
        "machine_set": "machines",
    }
    with pytest.raises(HTTPError):
        yield http_client.fetch(fe_url, method="POST",
                headers={"X-Grouper-User": plebe}, body=urlencode(update))

    # A group member can.
    resp = yield http_client.fetch(fe_url, method="POST",
                headers={"X-Grouper-User": owner}, body=urlencode(update))
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["service_account"]["description"] == "desc"
    assert metadata["service_account"]["machine_set"] == "machines"

    # A user admin also can.
    update["description"] = "done by admin"
    resp = yield http_client.fetch(fe_url, method="POST",
                headers={"X-Grouper-User": owner}, body=urlencode(update))
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["service_account"]["description"] == "done by admin"


@pytest.mark.gen_test
def test_service_account_fe_perms(session, standard_graph, http_client, base_url):
    graph = standard_graph
    admin = "tyleromeara@a.co"
    owner = "zay@a.co"
    plebe = "oliver@a.co"

    # Unrelated people cannot grant a permission.
    fe_url = url(base_url, "/groups/team-sre/service/service@a.co/grant")
    with pytest.raises(HTTPError):
        yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": plebe},
                body=urlencode({"permission": "team-sre", "argument": "*"}))

    # Even group owners cannot grant an unrelated permission.
    resp = yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": owner},
            body=urlencode({"permission": "other-perm", "argument": "*"}))
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.get_user_details("service@a.co")
    assert metadata["permissions"] == []

    # Group owners can delegate a team permission.
    resp = yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": owner},
            body=urlencode({"permission": "team-sre", "argument": "*"}))
    assert resp.code == 200

    # Global user admins still cannot grant an unrelated permission.
    resp = yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": admin},
            body=urlencode({"permission": "other-perm", "argument": "*"}))
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.get_user_details("service@a.co")
    assert len(metadata["permissions"]) == 1

    # But can delegate a team permission.
    resp = yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": admin},
            body=urlencode({"permission": "ssh", "argument": "*"}))
    assert resp.code == 200

    # Check that the permissions are reflected in the graph.
    graph.update_from_db(session)
    metadata = graph.get_user_details("service@a.co")
    permissions = [(p["permission"], p["argument"]) for p in metadata["permissions"]]
    assert sorted(permissions) == [("ssh", "*"), ("team-sre", "*")]

    # Find the mapping IDs of the two permissions.
    service_account = ServiceAccount.get(session, name="service@a.co")
    permissions = service_account_permissions(session, service_account)

    # Unrelated people cannot revoke a permission.
    fe_url = url(base_url, "/groups/team-sre/service/service@a.co/revoke/{}".format(
        permissions[0].mapping_id))
    with pytest.raises(HTTPError):
        yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": plebe},
                body=urlencode({}))

    # But the group owner and a global admin can.
    resp = yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": admin},
            body=urlencode({}))
    assert resp.code == 200
    fe_url = url(base_url, "/groups/team-sre/service/service@a.co/revoke/{}".format(
        permissions[1].mapping_id))
    resp = yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": owner},
            body=urlencode({}))
    assert resp.code == 200

    # This should have removed all the permissions.
    graph.update_from_db(session)
    metadata = graph.get_user_details("service@a.co")
    assert metadata["permissions"] == []


class MachineSetPlugin(BasePlugin):
    """Test plugin that rejects some machine sets."""

    def check_machine_set(self, name, machine_set):
        # type: (str, str) -> None
        if "okay" not in machine_set:
            raise PluginRejectedMachineSet("{} has invalid machine set".format(name))


@pytest.mark.gen_test
def test_machine_set_plugin(mocker, session, standard_graph, http_client, base_url):
    mocker.patch(
        'grouper.service_account.get_plugin_proxy',
        return_value=PluginProxy([MachineSetPlugin()]),
    )

    graph = standard_graph
    admin = "zorkian@a.co"

    # Edit the metadata of an existing service account.  This should fail (although return 200)
    # including the appropriate error.
    update = {
        "description": "some service account",
        "machine_set": "not valid",
    }
    fe_url = url(base_url, "/groups/team-sre/service/service@a.co/edit")
    resp = yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": admin},
            body=urlencode(update))
    assert resp.code == 200
    assert "service@a.co has invalid machine set" in resp.body
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["service_account"]["machine_set"] == "some machines"

    # Use a valid machine set, and then this should go through.
    update["machine_set"] = "is okay"
    resp = yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": admin},
            body=urlencode(update))
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["service@a.co"]
    assert metadata["service_account"]["machine_set"] == "is okay"

    # Try creating a new service account with an invalid machine set.
    data = {
        "name": "other@svc.localhost",
        "description": "some other service account",
        "machine_set": "not valid",
    }
    fe_url = url(base_url, "/groups/team-sre/service/create")
    resp = yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": admin},
            body=urlencode(data))
    assert resp.code == 200
    assert "other@svc.localhost has invalid machine set" in resp.body
    graph.update_from_db(session)
    assert "other@svc.localhost" not in graph.users

    # But this should go through with a valid machine set.
    data["machine_set"] = "is okay"
    resp = yield http_client.fetch(fe_url, method="POST", headers={"X-Grouper-User": admin},
            body=urlencode(data))
    assert resp.code == 200
    graph.update_from_db(session)
    metadata = graph.user_metadata["other@svc.localhost"]
    assert metadata["service_account"]["description"] == "some other service account"
    assert metadata["service_account"]["machine_set"] == "is okay"
