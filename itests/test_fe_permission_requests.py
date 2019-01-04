import pytest

from fixtures import async_server, browser

from grouper.constants import PERMISSION_ADMIN, PERMISSION_GRANT
from grouper.models.permission import Permission
from grouper.models.permission_request import PermissionRequest
from grouper.permissions import create_request, update_request

from pages.exceptions import NoSuchElementException
from pages.permission_requests import PermissionRequestsPage, RequestViewRow, StatusChangeRow

from tests.fixtures import (
    graph, groups, service_accounts, permissions, session, standard_graph, users
)
from tests.url_util import url
from tests.util import grant_permission

# Set up a permission requesting scenario in which REQUESTING_USER has both
# inbound and outbound requests that they should be able to see on the requests
# page. Do this because the itest infrastructure visits all pages as cbguder.
PERM_WITH_GRANTER = 'perm.hasgranter'
PERM_NO_GRANTER = 'perm.nogranter'
ARGUMENT = 'a'
REASON = 'because reasons'
COMMENT = 'why actioned/cancelled'
GRANTING_TEAM = 'auditors'
GRANTING_USER = 'zorkian@a.co'
REQUESTING_TEAM = 'group-admins'
REQUESTING_USER = 'cbguder@a.co'
ADMIN_TEAM = 'group-admins'
ADMIN_USER = 'cbguder@a.co'

@pytest.fixture
def do_request_perms(groups, permissions, session, users):
    # Create the two test perms + PERMISSION_GRANT + PERMISSION_ADMIN, give GRANTING_TEAM
    # appropriate PERMISSION_GRANT, and make sure there's an admin (has PERMISSION_ADMIN)
    test_perm_granter = Permission.get_or_create(
        session, name=PERM_WITH_GRANTER, description='perm with granter')[0]
    test_perm_nogranter = Permission.get_or_create(
        session, name=PERM_NO_GRANTER, description='perm without granter')[0]
    grant_perm = Permission.get_or_create(session, name=PERMISSION_GRANT, description='')[0]
    admin_perm = Permission.get_or_create(session, name=PERMISSION_ADMIN, description='')[0]

    session.commit()

    grant_permission(groups[GRANTING_TEAM], grant_perm,
                     argument='{}/{}'.format(PERM_WITH_GRANTER, ARGUMENT))
    grant_permission(groups[ADMIN_TEAM], admin_perm, argument="")

    # Request the two test perms from REQUESTING_TEAM
    create_request(session, users[REQUESTING_USER], groups[REQUESTING_TEAM],
                   test_perm_granter, ARGUMENT, REASON)
    create_request(session, users[REQUESTING_USER], groups[REQUESTING_TEAM],
                   test_perm_nogranter, ARGUMENT, REASON)

    session.commit()


@pytest.fixture
def do_action_requests(session, permissions, users, do_request_perms):
    # Action (approve) the request for PERM_WITH_GRANTER, and
    # cancel (deny) the request for PERM_NO_GRANTER.
    all_requests = session.query(PermissionRequest)
    for request in all_requests:
        if request.status == 'pending' and request.permission.name == PERM_WITH_GRANTER:
            update_request(session, request, users[GRANTING_USER], 'actioned', REASON)
        if request.status == 'pending' and request.permission.name == PERM_NO_GRANTER:
            update_request(session, request, users[ADMIN_USER], 'cancelled', REASON)

    session.commit()


def test_pending_inbound_requests(async_server, browser, do_request_perms):
    fe_url = url(async_server, "/permissions/requests?status=pending")
    browser.get(fe_url)

    # Check that the request rows have info we expect
    page = PermissionRequestsPage(browser)
    request_rows = page.request_rows
    expected_perms = [
        '{}, {}'.format(PERM_WITH_GRANTER, ARGUMENT),
        '{}, {}'.format(PERM_NO_GRANTER, ARGUMENT)
    ]
    request_perms = [row.requested for row in request_rows]
    assert sorted(expected_perms) == sorted(request_perms)

    # Check the status change rows as well
    sc_rows = page.status_change_rows
    expected_groups = [REQUESTING_TEAM, REQUESTING_TEAM]
    request_groups = [row.group for row in sc_rows]
    assert expected_groups == request_groups
            
    # and make sure the "no requests" row doesn't show up
    with pytest.raises(Exception):
        dne_row = page.no_requests_row


def test_completed_inbound_requests(async_server, browser, do_action_requests):
    fe_url = url(async_server, "/permissions/requests?")
    browser.get(fe_url)

    # Check that the request rows have info we expect
    page = PermissionRequestsPage(browser)
    request_rows = page.request_rows
    expected_perms = [
        '{}, {}'.format(PERM_WITH_GRANTER, ARGUMENT),
        '{}, {}'.format(PERM_NO_GRANTER, ARGUMENT)
    ]
    request_perms = [row.requested for row in request_rows]
    assert sorted(expected_perms) == sorted(request_perms)

    # Check the status change rows as well
    sc_rows = page.status_change_rows
    expected_whos = ([REQUESTING_USER] * 3) + [GRANTING_USER]
    expected_whos = ['{} (now)'.format(user) for user in expected_whos]
    request_whos = [row.who for row in sc_rows]
    assert sorted(expected_whos) == sorted(request_whos)
            
    # and make sure the "no requests" row doesn't show up
    with pytest.raises(Exception):
        dne_row = page.no_requests_row

def test_no_requests(async_server, browser, do_action_requests):
    fe_url = url(async_server, "/permissions/requests?status=pending")
    browser.get(fe_url)

    page = PermissionRequestsPage(browser)
    assert page.no_requests_row is not None

    assert len(page.request_rows) == 0
    assert len(page.status_change_rows) == 0
