from mock import patch
import pytest

from constants import SSH_KEY_1
from ctl_util import call_main
from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from grouper.constants import GROUP_ADMIN, PERMISSION_ADMIN, USER_ADMIN
from grouper.models.base.model_base import Model
from grouper.models.group import Group
from grouper.models.user import User
from grouper.public_key import get_public_keys_of_user

noop = lambda *k: None


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
@patch('grouper.ctl.group.make_session')
def test_user_status_changes(make_user_session, make_group_session, session, users, groups):
    make_user_session.return_value = session
    make_group_session.return_value = session

    username = 'zorkian@a.co'
    groupname = 'team-sre'

    # add user to a group
    call_main('group', 'add_member', '--member', groupname, username)

    # disable the account
    call_main('user', 'disable', username)
    assert not User.get(session, name=username).enabled

    # double disabling is a no-op
    call_main('user', 'disable', username)
    assert not User.get(session, name=username).enabled

    # re-enable the account, preserving memberships
    call_main('user', 'enable', '--preserve-membership', username)
    assert User.get(session, name=username).enabled
    assert (u'User', username) in groups[groupname].my_members()

    # enabling an active account is a no-op
    call_main('user', 'enable', username)
    assert User.get(session, name=username).enabled

    # disable and re-enable without the --preserve-membership flag
    call_main('user', 'disable', username)
    call_main('user', 'enable', username)
    assert User.get(session, name=username).enabled
    assert (u'User', username) not in groups[groupname].my_members()


@patch('grouper.ctl.user.make_session')
def test_user_public_key(make_session, session, users):
    make_session.return_value = session

    # good key
    username = 'zorkian@a.co'
    call_main('user', 'add_public_key', username, SSH_KEY_1)

    user = User.get(session, name=username)
    keys = get_public_keys_of_user(session, user.id)
    assert len(keys) == 1
    assert keys[0].public_key == SSH_KEY_1

    # bad key
    call_main('user', 'add_public_key', username, SSH_KEY_1)

    keys = get_public_keys_of_user(session, user.id)
    assert len(keys) == 1
    assert keys[0].public_key == SSH_KEY_1


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


@patch('grouper.ctl.oneoff.Annex')
@patch('grouper.ctl.oneoff.make_session')
def test_oneoff(mock_make_session, mock_annex, session):
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
