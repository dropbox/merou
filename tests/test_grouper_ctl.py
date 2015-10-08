from mock import patch

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from grouper.ctl.main import main
from grouper.models import User


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
