from mock import patch
import pytest

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from grouper.constants import (
        GROUP_ADMIN,
        PERMISSION_ADMIN,
        SYSTEM_PERMISSIONS,
        USER_ADMIN,
)

from grouper.ctl.main import main
from grouper.models import Group, Model, User


noop = lambda *k: None


def call_main(*args):
    argv = ['grouper-ctl'] + list(args)
    return main(sys_argv=argv, start_config_thread=False)

@patch('grouper.ctl.user.make_session')
def test_user_create(make_session, session, users):
    make_session.return_value = session

    # simple
    username = 'john@a.co'
    call_main('user', 'create', username)
    assert User.get(session, name=username), 'non-existent user should be created'

    # check username
    bad_username = 'not_a_valid_username'
    call_main('user', 'create', bad_username)
    assert not User.get(session, name=bad_username), 'bad user should not be created'

    # bulk
    usernames = ['mary@a.co', 'sam@a.co', 'tina@a.co']
    call_main('user', 'create', *usernames)
    users = [User.get(session, name=u) for u in usernames]
    assert all(users), 'all users created'

    usernames_with_one_bad = ['kelly@a.co', 'brad@a.co', 'not_valid_user']
    call_main('user', 'create', *usernames_with_one_bad)
    users = [User.get(session, name=u) for u in usernames_with_one_bad]
    assert not any(users), 'one bad seed means no users created'


@patch('grouper.ctl.user.make_session')
def test_user_public_key(make_session, session, users):
    make_session.return_value = session

    # good key
    username = 'zorkian@a.co'
    good_key = ('ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDCUQeasspT/etEJR2WUoR+h2sMOQYbJgr0Q'
            'E+J8p97gEhmz107KWZ+3mbOwyIFzfWBcJZCEg9wy5Paj+YxbGONqbpXAhPdVQ2TLgxr41bNXvbcR'
            'AxZC+Q12UZywR4Klb2kungKz4qkcmSZzouaKK12UxzGB3xQ0N+3osKFj3xA1+B6HqrVreU19XdVo'
            'AJh0xLZwhw17/NDM+dAcEdMZ9V89KyjwjraXtOVfFhQF0EDF0ame8d6UkayGrAiXC2He0P2Cja+J'
            '371P27AlNLHFJij8WGxvcGGSeAxMLoVSDOOllLCYH5UieV8mNpX1kNe2LeA58ciZb0AXHaipSmCH'
            'gh/ some-comment')
    call_main('user', 'add_public_key', username, good_key)

    user = User.get(session, name=username)
    keys = user.my_public_keys()
    assert len(keys) == 1
    assert keys[0].public_key == good_key

    # bad key
    username = 'zorkian@a.co'
    bad_key = 'ssh-rsa AAAblahblahkey some-comment'
    call_main('user', 'add_public_key', username, good_key)

    user = User.get(session, name=username)
    keys = user.my_public_keys()
    assert len(keys) == 1
    assert keys[0].public_key == good_key


@patch('grouper.ctl.group.make_session')
def test_group_add_remove_member(make_session, session, users, groups):
    make_session.return_value = session

    username = 'oliver@a.co'
    groupname = 'team-sre'

    # add
    assert (u'User', username) not in groups[groupname].my_members()
    call_main('group', 'add_member', groupname, username)
    assert (u'User', username) in Group.get(session, name=groupname).my_members()

    # remove
    call_main('group', 'remove_member', groupname, username)
    assert (u'User', username) not in Group.get(session, name=groupname).my_members()

    # bulk add
    usernames = {'oliver@a.co', 'testuser@a.co', 'zebu@a.co'}
    call_main('group', 'add_member', groupname, *usernames)
    members = {u for _, u in Group.get(session, name=groupname).my_members().keys()}
    assert usernames.issubset(members)

    # bulk remove
    call_main('group', 'remove_member', groupname, *usernames)
    members = {u for _, u in Group.get(session, name=groupname).my_members().keys()}
    assert not members.intersection(usernames)

    # check user/group name
    call_main('group', 'add_member', 'invalid group name', username)
    assert (u'User', username) not in Group.get(session, name=groupname).my_members()

    bad_username = 'not_a_valid_username'
    call_main('group', 'add_member', groupname , bad_username)
    assert (u'User', bad_username) not in Group.get(session, name=groupname).my_members()


@patch('grouper.ctl.sync_db.make_session')
@patch('grouper.ctl.sync_db.get_database_url', new=noop)
@patch('grouper.ctl.sync_db.get_db_engine', new=noop)
@patch.object(Model.metadata, 'create_all', new=noop)
def test_sync_db_default_group(make_session, session, users, groups):
    make_session.return_value = session

    call_main('sync_db')
    admin_group = Group.get(session, name="grouper-administrators")
    assert admin_group, "Group should have been autocreated"

    admin_group_permission_names = [perm[1] for perm in admin_group.my_permissions()]
    for permission in (GROUP_ADMIN, PERMISSION_ADMIN, USER_ADMIN):
        assert permission in admin_group_permission_names, \
                "Expected permission missing: %s" % permission


@patch('grouper.ctl.oneoff.load_plugins')
@patch('grouper.ctl.oneoff.Annex')
@patch('grouper.ctl.oneoff.make_session')
def test_oneoff(mock_make_session, mock_annex, mock_load_plugins, session):
    mock_make_session.return_value = session
    username = 'fake_user@a.co'
    other_username = 'fake_user2@a.co'
    groupname = 'fake_group'

    class FakeOneOff(object):
        def configure(self, service_name):
            pass

        def run(self, session, **kwargs):
            if kwargs.get('group'):
                Group.get_or_create(session, groupname=groupname)
                session.commit()
            elif kwargs.get('key') == 'valuewith=':
                User.get_or_create(session, username=other_username)
                session.commit()
            else:
                User.get_or_create(session, username=username)
                session.commit()

    mock_annex.return_value = [FakeOneOff()]

    # dry_run
    call_main('oneoff', 'run', 'FakeOneOff')
    assert User.get(session, name=username) is None, 'default dry_run means no writes'
    assert User.get(session, name=other_username) is None, '"valuewith= not in arg'
    assert Group.get(session, name=groupname) is None, '"group" not in arg so no group created'

    # not dry_run, create a user
    call_main('oneoff', 'run', '--no-dry_run', 'FakeOneOff')
    assert User.get(session, name=username) is not None, 'dry_run off means writes'
    assert User.get(session, name=other_username) is None, '"valuewith= not in arg'
    assert Group.get(session, name=groupname) is None, '"group" not in arg so no group created'

    # not dry_run, use kwarg to create a group
    call_main('oneoff', 'run', '--no-dry_run', 'FakeOneOff', 'group=1')
    assert User.get(session, name=username) is not None, 'dry_run off means writes'
    assert User.get(session, name=other_username) is None, '"valuewith= not in arg'
    assert Group.get(session, name=groupname) is not None, '"group" in arg so group created'

    # invalid format for argument should result in premature system exit
    with pytest.raises(SystemExit):
        call_main('oneoff', 'run', '--no-dry_run', 'FakeOneOff', 'bad_arg')

    call_main('oneoff', 'run', '--no-dry_run', 'FakeOneOff', 'key=valuewith=')
    assert User.get(session, name=other_username) is not None, '"valuewith= in arg, create user2'
