from mock import patch
from pytest import raises

from grouper.models.group import Group
from grouper.plugin.proxy import PluginProxy
from plugins.group_ownership_policy import GroupOwnershipPolicyPlugin
from tests.ctl_util import call_main
from tests.fixtures import graph, groups, permissions, session, standard_graph, users  # noqa: F401


@patch("grouper.user.get_plugin_proxy")
def test_group_disable_group_owner(get_plugin_proxy, session, tmpdir, users, groups):  # noqa: F811
    get_plugin_proxy.return_value = PluginProxy([GroupOwnershipPolicyPlugin()])

    username = "oliver@a.co"
    groupname = "team-sre"

    # add
    call_main(session, tmpdir, "group", "add_member", "--owner", groupname, username)
    assert ("User", username) in Group.get(session, name=groupname).my_members()

    # disable (fails)
    with raises(SystemExit):
        call_main(session, tmpdir, "user", "disable", username)
    assert ("User", username) in Group.get(session, name=groupname).my_members()
