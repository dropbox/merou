from mock import patch
import pytest

from ctl_util import call_main
from fixtures import standard_graph, graph, users, groups, service_accounts, session  # noqa
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount
from grouper.group_service_account import get_service_accounts


@patch('grouper.ctl.service_account.make_session')
def test_service_account_create(make_session, groups, service_accounts, session, users):
    make_session.return_value = session

    machine_set = 'foo +bar -(org)'
    description = 'this is a service account.\n\n it is for testing'
    security_team_group = Group.get(session, name='security-team')
    good_actor_username = 'gary@a.co'
    good_service_account_name = 'good-service@a.co'

    assert ServiceAccount.get(session, name=good_service_account_name) is None
    assert get_service_accounts(session, security_team_group) == []
    # no-op if non-existing actor
    call_main('service_account', '--actor', 'no-such-actor@a.co', 'create',
              good_service_account_name, security_team_group.groupname, machine_set, description)
    # ... or if bad account name
    call_main('service_account', '--actor', good_actor_username, 'create',
              'bad-service-account-name', security_team_group.groupname, machine_set, description)
    # ... or non-existing owner group
    call_main('service_account', '--actor', good_actor_username, 'create',
              good_service_account_name, 'non-such-owner-group', machine_set, description)
    # make sure no change was made
    assert ServiceAccount.get(session, name=good_service_account_name) is None
    assert get_service_accounts(session, security_team_group) == []

    # now it works
    call_main('service_account', '--actor', good_actor_username, 'create',
              good_service_account_name, security_team_group.groupname, machine_set, description)
    service_account = ServiceAccount.get(session, name=good_service_account_name)
    assert service_account, 'non-existing account should be created'
    assert service_account.user.name == good_service_account_name
    assert service_account.machine_set == machine_set
    assert service_account.description == description
    assert get_service_accounts(session, security_team_group) == [service_account]

    # no-op if account name already exists
    call_main('service_account', '--actor', good_actor_username, 'create',
              good_service_account_name, security_team_group.groupname, machine_set, description)
    service_account = ServiceAccount.get(session, name=good_service_account_name)
    assert service_account, 'non-account should be created'
    assert service_account.user.name == good_service_account_name
    assert service_account.machine_set == machine_set
    assert service_account.description == description
    assert get_service_accounts(session, security_team_group) == [service_account]

    # actor can be a service account as well
    call_main('service_account', '--actor', 'service@a.co', 'create',
              'service-2@a.co', security_team_group.groupname, machine_set + '2', description + '2')
    service_account_2 = ServiceAccount.get(session, name='service-2@a.co')
    assert service_account_2, 'non-existing account should be created'
    assert service_account_2.user.name == 'service-2@a.co'
    assert service_account_2.machine_set == (machine_set + '2')
    assert service_account_2.description == (description + '2')
    assert set(get_service_accounts(session, security_team_group)) == set(
        [service_account, service_account_2])
