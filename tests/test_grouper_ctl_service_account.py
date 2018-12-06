from mock import patch
import pytest

from ctl_util import call_main
from fixtures import standard_graph, graph, users, groups, session  # noqa
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount
from grouper.group_service_account import get_service_accounts


@patch('grouper.ctl.service_account.make_session')
def test_service_account_create(make_session, session, users, groups):
    make_session.return_value = session

    machine_set = 'foo +bar -(org)'
    description = 'this is a service account.\n\n it is for testing'
    team_sre_group = Group.get(session, name='team-sre')
    actor_username = 'gary@a.co'

    # no-op if bad account name
    name = 'bad'
    assert ServiceAccount.get(session, name=name) is None
    assert get_service_accounts(session, team_sre_group) == []
    call_main('service_account', '--actor', actor_username, 'create',
              name, team_sre_group.groupname, machine_set, description)
    assert ServiceAccount.get(session, name=name) is None
    assert get_service_accounts(session, team_sre_group) == []

    # no-op if owner group doesn't exist
    name = 'good@a.co'
    assert ServiceAccount.get(session, name=name) is None
    assert get_service_accounts(session, team_sre_group) == []
    call_main('service_account', '--actor', actor_username, 'create',
              name, 'this-group-does-not-exist', machine_set, description)
    assert ServiceAccount.get(session, name=name) is None
    assert get_service_accounts(session, team_sre_group) == []

    # now it works
    name = 'good@a.co'
    assert ServiceAccount.get(session, name=name) is None
    assert get_service_accounts(session, team_sre_group) == []
    actor_username = 'gary@a.co'
    call_main('service_account', '--actor', actor_username, 'create',
              name, team_sre_group.groupname, machine_set, description)
    service_account = ServiceAccount.get(session, name=name)
    assert service_account, 'non-account should be created'
    assert service_account.user.name == name
    assert service_account.machine_set == machine_set
    assert service_account.description == description
    assert get_service_accounts(session, team_sre_group) == [service_account]

    # no-op if account name already exists
    call_main('service_account', '--actor', actor_username, 'create',
              name, team_sre_group.groupname, machine_set, description)
    service_account = ServiceAccount.get(session, name=name)
    assert service_account, 'non-account should be created'
    assert service_account.user.name == name
    assert service_account.machine_set == machine_set
    assert service_account.description == description
    assert get_service_accounts(session, team_sre_group) == [service_account]

    
