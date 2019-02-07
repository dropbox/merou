from mock import patch

from ctl_util import call_main
from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from grouper.models.group import Group
from grouper.plugin.proxy import PluginProxy
from plugins.group_ownership_policy import GroupOwnershipPolicyPlugin


@patch("grouper.user.get_plugin_proxy")
@patch('grouper.ctl.group.make_session')
@patch('grouper.ctl.user.make_session')
def test_group_disable_group_owner(user_make_session, group_make_session, get_plugin_proxy, session,
                                   users, groups):
    group_make_session.return_value = session
    user_make_session.return_value = session
    get_plugin_proxy.return_value = PluginProxy([GroupOwnershipPolicyPlugin()])

    username = 'oliver@a.co'
    groupname = 'team-sre'

    # add
    call_main(session, 'group', 'add_member', '--owner', groupname, username)
    assert (u'User', username) in Group.get(session, name=groupname).my_members()

    # disable (fails)
    call_main(session, 'user', 'disable', username)
    assert (u'User', username) in Group.get(session, name=groupname).my_members()
