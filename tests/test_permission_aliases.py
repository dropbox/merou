import json

import pytest

from fixtures import api_app as app  # noqa
from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from grouper.models.counter import Counter
from grouper.plugin import PluginProxy
from plugins.permission_aliases import PermissionAliasesPlugin
from url_util import url


@pytest.mark.gen_test
def test_groups_aliased_permissions(mocker, session, standard_graph, http_client, base_url):
    proxy = PluginProxy([PermissionAliasesPlugin()])
    mocker.patch('grouper.graph.get_plugin_proxy', return_value=proxy)

    # Force graph update
    Counter.incr(session, "updates")
    standard_graph.update_from_db(session)

    api_url = url(base_url, '/groups/sad-team')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    permissions = [
        (p['permission'], p['argument'])
        for p in body['data']['permissions']
    ]

    assert ('owner', 'sad-team') in permissions
    assert ('ssh', 'owner=sad-team') in permissions
    assert ('sudo', 'sad-team') in permissions


@pytest.mark.gen_test
def test_users_aliased_permissions(mocker, session, standard_graph, http_client, base_url):
    proxy = PluginProxy([PermissionAliasesPlugin()])
    mocker.patch('grouper.graph.get_plugin_proxy', return_value=proxy)

    # Force graph update
    Counter.incr(session, "updates")
    standard_graph.update_from_db(session)

    api_url = url(base_url, '/users/zorkian@a.co')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    permissions = [
        (p['permission'], p['argument'])
        for p in body['data']['permissions']
    ]

    assert ('owner', 'sad-team') in permissions
    assert ('ssh', 'owner=sad-team') in permissions
    assert ('sudo', 'sad-team') in permissions


@pytest.mark.gen_test
def test_permissions_aliased_permissions(mocker, session, standard_graph, http_client, base_url):
    proxy = PluginProxy([PermissionAliasesPlugin()])
    mocker.patch('grouper.graph.get_plugin_proxy', return_value=proxy)

    # Force graph update
    Counter.incr(session, "updates")
    standard_graph.update_from_db(session)

    api_url = url(base_url, '/permissions/ssh')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    permissions = [
        (group, p['argument'])
        for group, g in body['data']['groups'].iteritems()
        for p in g['permissions']
    ]

    assert ('sad-team', 'owner=sad-team') in permissions
