from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from selenium.common.exceptions import NoSuchElementException

from grouper.constants import PERMISSION_ADMIN, PERMISSION_GRANT
from grouper.models.group import Group
from grouper.models.permission import Permission
from grouper.models.permission_request import PermissionRequest
from grouper.models.user import User
from grouper.permissions import create_request, update_request
from grouper.settings import set_global_settings
from itests.pages.permission_requests import PermissionRequestsPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def create_permission_requests(setup: SetupTest) -> None:
    """Create a permission requesting scenario.

    Set up a permission requesting scenario in which cbguder@a.co has both inbound and outbound
    requests that they should be able to see on the requests page.
    """
    with setup.transaction():
        setup.create_permission("perm.hasgranter", description="perm with granter")
        setup.create_permission("perm.nogranter", description="perm without granter")
        setup.add_user_to_group("zorkian@a.co", "auditors")
        setup.grant_permission_to_group(PERMISSION_GRANT, "perm.hasgranter/a", "auditors")
        setup.add_user_to_group("cbguder@a.co", "group-admins")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "group-admins")

    # The old API requires SQLAlchemy objects.
    granting_user = User.get(setup.session, name="zorkian@a.co")
    assert granting_user
    granting_group = Group.get(setup.session, name="auditors")
    assert granting_group
    requesting_user = User.get(setup.session, name="cbguder@a.co")
    assert requesting_user
    requesting_group = Group.get(setup.session, name="group-admins")
    assert requesting_group
    perm_granter = Permission.get(setup.session, "perm.hasgranter")
    assert perm_granter
    perm_nogranter = Permission.get(setup.session, "perm.nogranter")
    assert perm_nogranter
    perm_admin = Permission.get(setup.session, PERMISSION_ADMIN)
    assert perm_admin

    # The old APIs require a global settings object.
    set_global_settings(setup.settings)

    # Request the two test perms from group-admins.
    with setup.transaction():
        create_request(
            setup.session, requesting_user, requesting_group, perm_granter, "a", "reasons"
        )
        create_request(
            setup.session, requesting_user, requesting_group, perm_nogranter, "a", "reasons"
        )

    # Finally make one more request from a user other than cbguder@a.co.
    with setup.transaction():
        create_request(setup.session, granting_user, granting_group, perm_admin, "a", "reasons")


def action_permission_requests(setup: SetupTest) -> None:
    """Action (approve) the perm.hasgranter request, cancel (deny) the perm.nogranter request."""
    granting_user = User.get(setup.session, name="zorkian@a.co")
    assert granting_user
    admin_user = User.get(setup.session, name="cbguder@a.co")
    assert admin_user

    with setup.transaction():
        all_requests = setup.session.query(PermissionRequest)
        for request in all_requests:
            if request.status == "pending" and request.permission.name == "perm.hasgranter":
                update_request(setup.session, request, granting_user, "actioned", "reasons")
            if request.status == "pending" and request.permission.name == "perm.nogranter":
                update_request(setup.session, request, admin_user, "cancelled", "reasons")


def test_pending_inbound_requests(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    create_permission_requests(setup)

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/requests?status=pending"))
        page = PermissionRequestsPage(browser)

        # Check the request rows.
        requested = [row.requested for row in page.request_rows]
        expected = ["perm.hasgranter, a", "perm.nogranter, a", f"{PERMISSION_ADMIN}, a"]
        assert sorted(requested) == sorted(expected)

        # Check the status change rows.
        groups = [row.group for row in page.status_change_rows]
        assert sorted(groups) == ["auditors", "group-admins", "group-admins"]

        # Make sure the "no requests" row doesn't show up.
        with pytest.raises(NoSuchElementException):
            page.no_requests_row


def assert_valid_status_timestamp(when: str) -> None:
    """Check the timestamp of a status change row.

    The timestamp part of the row is normally "(now)" but can be "(1 second ago)" or more on slow
    systems and "(in the future)" if MySQL rounds the timestamp up.  Allow for all of these.
    """
    if when in ("(now)", "(in the future)"):
        return
    assert re.match(r"^\([0-9] seconds? ago\)$", when) is not None, f"{when} does not match"


def test_completed_inbound_requests(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    create_permission_requests(setup)
    action_permission_requests(setup)

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/requests"))
        page = PermissionRequestsPage(browser)

        requested = [row.requested for row in page.request_rows]
        expected = ["perm.hasgranter, a", "perm.nogranter, a", f"{PERMISSION_ADMIN}, a"]
        assert sorted(requested) == sorted(expected)

        whos = []
        for row in page.status_change_rows:
            who, when = row.who.split(None, 1)
            assert_valid_status_timestamp(when)
            whos.append(who)
        assert sorted(whos) == sorted(["cbguder@a.co"] * 3 + ["zorkian@a.co"] * 2)

        # Make sure the "no requests" row doesn't show up.
        with pytest.raises(NoSuchElementException):
            page.no_requests_row


def test_outbound_requests(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    create_permission_requests(setup)

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/requests?direction=Requested+by+me"))
        page = PermissionRequestsPage(browser)

        # Check that the request rows have info we expect, namely the 2 requests made by
        # cbguder@a.co but not the one request made by another user.
        requested = [row.requested for row in page.request_rows]
        assert sorted(requested) == ["perm.hasgranter, a", "perm.nogranter, a"]

        # Check the status change rows.
        request_groups = [row.group for row in page.status_change_rows]
        assert sorted(request_groups) == ["group-admins", "group-admins"]

        # Make sure the "no requests" row doesn't show up.
        with pytest.raises(NoSuchElementException):
            page.no_requests_row


def test_no_requests(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    create_permission_requests(setup)
    action_permission_requests(setup)

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        request_url = "/permissions/requests?status=pending&direction=Requested+by+me"
        browser.get(url(frontend_url, request_url))
        page = PermissionRequestsPage(browser)

        assert page.no_requests_row is not None
        assert len(page.request_rows) == 0
        assert len(page.status_change_rows) == 0
