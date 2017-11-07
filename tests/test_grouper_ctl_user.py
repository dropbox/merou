from mock import patch

from ctl_util import call_main
from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from grouper.models.group import Group
from plugins.group_ownership_policy import GroupOwnershipPolicyPlugin


@patch("grouper.user.get_plugins")
@patch('grouper.ctl.group.make_session')
@patch('grouper.ctl.user.make_session')
def test_group_disable_group_owner(user_make_session, group_make_session, get_plugins, session,
                                   users, groups):
    group_make_session.return_value = session
    user_make_session.return_value = session
    get_plugins.return_value = [GroupOwnershipPolicyPlugin()]

    username = 'oliver@a.co'
    groupname = 'team-sre'

    # add
    call_main('group', 'add_member', '--owner', groupname, username)
    assert (u'User', username) in Group.get(session, name=groupname).my_members()

    # disable (fails)
    call_main('user', 'disable', username)
    assert (u'User', username) in Group.get(session, name=groupname).my_members()
