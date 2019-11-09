import pytest
from mock import patch

from grouper.models.group import Group
from grouper.models.user import User
from grouper.public_key import get_public_keys_of_user
from tests.constants import SSH_KEY_1, SSH_KEY_BAD
from tests.ctl_util import call_main
from tests.fixtures import graph, groups, permissions, session, standard_graph, users  # noqa: F401


def test_user_create(session, tmpdir, users):  # noqa: F811
    # simple
    username = "john@a.co"
    call_main(session, tmpdir, "user", "create", username)
    assert User.get(session, name=username), "non-existent user should be created"

    # check username
    bad_username = "not_a_valid_username"
    call_main(session, tmpdir, "user", "create", bad_username)
    assert not User.get(session, name=bad_username), "bad user should not be created"

    # bulk
    usernames = ["mary@a.co", "sam@a.co", "tina@a.co"]
    call_main(session, tmpdir, "user", "create", *usernames)
    users = [User.get(session, name=u) for u in usernames]
    assert all(users), "all users created"

    usernames_with_one_bad = ["kelly@a.co", "brad@a.co", "not_valid_user"]
    call_main(session, tmpdir, "user", "create", *usernames_with_one_bad)
    users = [User.get(session, name=u) for u in usernames_with_one_bad]
    assert not any(users), "one bad seed means no users created"


def test_user_status_changes(session, tmpdir, users, groups):  # noqa: F811
    username = "zorkian@a.co"
    groupname = "team-sre"

    # add user to a group
    call_main(session, tmpdir, "group", "add_member", "--member", groupname, username)

    # disable the account
    call_main(session, tmpdir, "user", "disable", username)
    assert not User.get(session, name=username).enabled

    # double disabling is a no-op
    call_main(session, tmpdir, "user", "disable", username)
    assert not User.get(session, name=username).enabled

    # re-enable the account, preserving memberships
    call_main(session, tmpdir, "user", "enable", "--preserve-membership", username)
    assert User.get(session, name=username).enabled
    assert ("User", username) in groups[groupname].my_members()

    # enabling an active account is a no-op
    call_main(session, tmpdir, "user", "enable", username)
    assert User.get(session, name=username).enabled

    # disable and re-enable without the --preserve-membership flag
    call_main(session, tmpdir, "user", "disable", username)
    call_main(session, tmpdir, "user", "enable", username)
    assert User.get(session, name=username).enabled
    assert ("User", username) not in groups[groupname].my_members()


def test_user_public_key(session, tmpdir, users):  # noqa: F811
    # good key
    username = "zorkian@a.co"
    call_main(session, tmpdir, "user", "add_public_key", username, SSH_KEY_1)

    user = User.get(session, name=username)
    keys = get_public_keys_of_user(session, user.id)
    assert len(keys) == 1
    assert keys[0].public_key == SSH_KEY_1

    # duplicate key
    call_main(session, tmpdir, "user", "add_public_key", username, SSH_KEY_1)

    keys = get_public_keys_of_user(session, user.id)
    assert len(keys) == 1
    assert keys[0].public_key == SSH_KEY_1

    # bad key
    call_main(session, tmpdir, "user", "add_public_key", username, SSH_KEY_BAD)

    keys = get_public_keys_of_user(session, user.id)
    assert len(keys) == 1
    assert keys[0].public_key == SSH_KEY_1


@patch("grouper.ctl.oneoff.load_plugins")
def test_oneoff(mock_load_plugins, session, tmpdir):  # noqa: F811
    username = "fake_user@a.co"
    other_username = "fake_user2@a.co"
    groupname = "fake_group"

    class FakeOneOff:
        def configure(self, service_name):
            pass

        def run(self, session, **kwargs):
            if kwargs.get("group"):
                Group.get_or_create(session, groupname=groupname)
                session.commit()
            elif kwargs.get("key") == "valuewith=":
                User.get_or_create(session, username=other_username)
                session.commit()
            else:
                User.get_or_create(session, username=username)
                session.commit()

    mock_load_plugins.return_value = [FakeOneOff()]

    # dry_run
    call_main(session, tmpdir, "oneoff", "run", "FakeOneOff")
    assert User.get(session, name=username) is None, "default dry_run means no writes"
    assert User.get(session, name=other_username) is None, '"valuewith= not in arg'
    assert Group.get(session, name=groupname) is None, '"group" not in arg so no group created'

    # not dry_run, create a user
    call_main(session, tmpdir, "oneoff", "run", "--no-dry_run", "FakeOneOff")
    assert User.get(session, name=username) is not None, "dry_run off means writes"
    assert User.get(session, name=other_username) is None, '"valuewith= not in arg'
    assert Group.get(session, name=groupname) is None, '"group" not in arg so no group created'

    # not dry_run, use kwarg to create a group
    call_main(session, tmpdir, "oneoff", "run", "--no-dry_run", "FakeOneOff", "group=1")
    assert User.get(session, name=username) is not None, "dry_run off means writes"
    assert User.get(session, name=other_username) is None, '"valuewith= not in arg'
    assert Group.get(session, name=groupname) is not None, '"group" in arg so group created'

    # invalid format for argument should result in premature system exit
    with pytest.raises(SystemExit):
        call_main(session, tmpdir, "oneoff", "run", "--no-dry_run", "FakeOneOff", "bad_arg")

    call_main(session, tmpdir, "oneoff", "run", "--no-dry_run", "FakeOneOff", "key=valuewith=")
    assert User.get(session, name=other_username) is not None, '"valuewith= in arg, create user2'
