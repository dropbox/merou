from datetime import datetime
from time import time
from typing import TYPE_CHECKING

from grouper.constants import PERMISSION_CREATE
from grouper.entities.permission import Permission
from grouper.fe.template_util import print_date
from itests.pages.permission_view import PermissionViewPage
from itests.pages.permissions import PermissionsPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py.path import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest
    from typing import List


def create_test_data(setup):
    # type: (SetupTest) -> List[Permission]
    """Sets up a very basic test graph and returns the permission objects.

    Be careful not to include milliseconds in the creation timestamps since this causes different
    behavior on SQLite (which preserves them) and MySQL (which drops them).
    """
    early_date = datetime.utcfromtimestamp(1)
    now_minus_one_second = datetime.utcfromtimestamp(int(time() - 1))
    now = datetime.utcfromtimestamp(int(time()))
    permissions = [
        Permission(
            name="first-permission",
            description="first",
            created_on=now_minus_one_second,
            audited=False,
            enabled=True,
        ),
        Permission(
            name="audited-permission", description="", created_on=now, audited=True, enabled=True
        ),
        Permission(
            name="early-permission",
            description="is early",
            created_on=early_date,
            audited=False,
            enabled=True,
        ),
    ]
    with setup.transaction():
        for permission in permissions:
            setup.create_permission(
                name=permission.name,
                description=permission.description,
                created_on=permission.created_on,
                audited=permission.audited,
            )
        setup.create_permission("disabled", enabled=False)
        setup.create_user("gary@a.co")
    return permissions


def test_list(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    permissions = create_test_data(setup)
    expected_permissions = [(p.name, p.description, print_date(p.created_on)) for p in permissions]

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions"))

        # Check the basic permission list.
        page = PermissionsPage(browser)
        seen_permissions = [(r.name, r.description, r.created_on) for r in page.permission_rows]
        assert seen_permissions == sorted(expected_permissions)
        assert page.heading == "Permissions"
        assert page.subheading == "{} permission(s)".format(len(expected_permissions))
        assert page.limit_label == "Limit: 100"

        # Switch to only audited permissions.
        page.click_show_audited_button()
        seen_permissions = [(r.name, r.description, r.created_on) for r in page.permission_rows]
        audited = [p for p in expected_permissions if p[0] == "audited-permission"]
        assert seen_permissions == sorted(audited)
        assert page.heading == "Audited Permissions"
        assert page.subheading == "{} permission(s)".format(len(audited))

        # Switch back to all permissions and sort by date.
        page.click_show_all_button()
        page.click_sort_by_date()
        seen_permissions = [(r.name, r.description, r.created_on) for r in page.permission_rows]
        expected_permissions_sorted_by_time = [
            (p.name, p.description, print_date(p.created_on))
            for p in sorted(permissions, key=lambda p: p.created_on, reverse=True)
        ]
        assert seen_permissions == expected_permissions_sorted_by_time

        # Reverse the sort order.
        page.click_sort_by_date()
        seen_permissions = [(r.name, r.description, r.created_on) for r in page.permission_rows]
        assert seen_permissions == list(reversed(expected_permissions_sorted_by_time))


def test_list_pagination(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    """Test pagination.

    This forces the pagination to specific values, rather than using the page controls, since we
    don't create more than 100 permissions for testing.
    """
    permissions = create_test_data(setup)
    expected_permissions = [(p.name, p.description, print_date(p.created_on)) for p in permissions]
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions?limit=1&offset=1"))
        page = PermissionsPage(browser)
        seen_permissions = [(r.name, r.description, r.created_on) for r in page.permission_rows]
        assert seen_permissions == sorted(expected_permissions)[1:2]
        assert page.limit_label == "Limit: 1"

        # Retrieve the last permission but with a larger limit to test that the limit isn't capped
        # to the number of returned items.
        browser.get(url(frontend_url, "/permissions?limit=10&offset=2"))
        page = PermissionsPage(browser)
        seen_permissions = [(r.name, r.description, r.created_on) for r in page.permission_rows]
        assert seen_permissions == sorted(expected_permissions)[2:]
        assert page.limit_label == "Limit: 10"


def test_list_create_button(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_user("gary@a.co")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions"))
        page = PermissionsPage(browser)
        assert not page.has_create_permission_button

        with setup.transaction():
            setup.grant_permission_to_group(PERMISSION_CREATE, "*", "admins")
            setup.add_user_to_group("gary@a.co", "admins")
        browser.get(url(frontend_url, "/permissions?refresh=yes"))
        assert page.has_create_permission_button


def test_view(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_permission("audited-permission", "", audited=True)
        setup.create_permission("some-permission", "Some permission")
        setup.grant_permission_to_group("some-permission", "", "another-group")
        setup.grant_permission_to_group("some-permission", "foo", "some-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/some-permission"))
        page = PermissionViewPage(browser)
        assert page.subheading == "some-permission"
        assert page.description == "Some permission"
        assert not page.has_disable_permission_button
        assert not page.has_disable_auditing_button
        assert not page.has_enable_auditing_button
        assert not page.has_audited_warning

        grants = [(r.group, r.argument) for r in page.permission_grant_rows]
        assert grants == [("another-group", "(unargumented)"), ("some-group", "foo")]

        browser.get(url(frontend_url, "/permissions/audited-permission"))
        page = PermissionViewPage(browser)
        assert page.subheading == "audited-permission"
        assert not page.description
        assert page.has_audited_warning
        assert not page.has_disable_auditing_button
        assert not page.has_enable_auditing_button
        assert page.has_no_grants
