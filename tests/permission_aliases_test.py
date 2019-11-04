import json

import pytest

from grouper.models.counter import Counter
from grouper.plugin import PluginProxy
from plugins.test_permission_aliases import TestPermissionAliasesPlugin
from tests.fixtures import (  # noqa: F401
    api_app as app,
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)
from tests.url_util import url


@pytest.mark.gen_test
def test_groups_aliased_permissions(
    mocker, session, standard_graph, http_client, base_url  # noqa: F811
):
    proxy = PluginProxy([TestPermissionAliasesPlugin()])
    mocker.patch("grouper.graph.get_plugin_proxy", return_value=proxy)

    # Force graph update
    Counter.incr(session, "updates")
    standard_graph.update_from_db(session)

    api_url = url(base_url, "/groups/sad-team")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    perms = [(p["permission"], p["argument"]) for p in body["data"]["permissions"]]

    assert ("owner", "sad-team") in perms
    assert ("ssh", "owner=sad-team") in perms
    assert ("sudo", "sad-team") in perms


@pytest.mark.gen_test
def test_users_aliased_permissions(
    mocker, session, standard_graph, http_client, base_url  # noqa: F811
):
    proxy = PluginProxy([TestPermissionAliasesPlugin()])
    mocker.patch("grouper.graph.get_plugin_proxy", return_value=proxy)

    # Force graph update
    Counter.incr(session, "updates")
    standard_graph.update_from_db(session)

    api_url = url(base_url, "/users/zorkian@a.co")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    perms = [(p["permission"], p["argument"]) for p in body["data"]["permissions"]]

    assert ("owner", "sad-team") in perms
    assert ("ssh", "owner=sad-team") in perms
    assert ("sudo", "sad-team") in perms


@pytest.mark.gen_test
def test_permissions_aliased_permissions(
    mocker, session, standard_graph, http_client, base_url  # noqa: F811
):
    proxy = PluginProxy([TestPermissionAliasesPlugin()])
    mocker.patch("grouper.graph.get_plugin_proxy", return_value=proxy)

    # Force graph update
    Counter.incr(session, "updates")
    standard_graph.update_from_db(session)

    api_url = url(base_url, "/permissions/ssh")
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    perms = [
        (group, p["argument"])
        for group, g in body["data"]["groups"].items()
        for p in g["permissions"]
    ]

    assert ("sad-team", "owner=sad-team") in perms
