from typing import TYPE_CHECKING

from grouper.constants import PERMISSION_CREATE
from grouper.fe.settings import settings
from grouper.fe.template_util import print_date
from grouper.permissions import create_permission, grant_permission
from itests.fixtures import async_server, browser  # noqa: F401
from itests.pages.permissions import PermissionsPage
from tests.fixtures import (  # noqa: F401
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)
from tests.url_util import url

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.models.group import Group
    from grouper.models.permission import Permission as Permission
    from selenium.webdriver import Chrome
    from typing import Dict


def test_list(async_server, browser, permissions, session):  # noqa: F811
    # type: (str, Chrome, Dict[str, Permission], Session) -> None
    settings.override_timezone("UTC")
    fe_url = url(async_server, "/permissions")
    browser.get(fe_url)

    # Check the basic permission list.
    page = PermissionsPage(browser)
    seen_permissions = [(r.name, r.description, r.created_on) for r in page.permission_rows]
    expected_permissions = [
        (p.name, p.description, print_date(p.created_on)) for p in permissions.values()
    ]
    assert seen_permissions == sorted(expected_permissions)
    assert page.heading == "Permissions"
    assert page.subheading == "{} permission(s)".format(len(permissions))

    # Switch to only audited permissions.
    page.click_show_audited_button()
    seen_permissions = [(r.name, r.description, r.created_on) for r in page.permission_rows]
    audited_permissions = [
        (p.name, p.description, print_date(p.created_on))
        for p in permissions.values()
        if p._audited
    ]
    assert seen_permissions == sorted(audited_permissions)
    assert page.heading == "Audited Permissions"
    assert page.subheading == "{} permission(s)".format(len(audited_permissions))

    # Switch back to all permissions and sort by date.
    page.click_show_all_button()
    page.click_sort_by_date()
    seen_permissions = [(r.name, r.description, r.created_on) for r in page.permission_rows]
    expected_permissions = [
        (p.name, p.description, print_date(p.created_on))
        for p in sorted(permissions.values(), key=lambda p: p.created_on, reverse=True)
    ]
    assert seen_permissions == expected_permissions

    # Reverse the sort order.
    page.click_sort_by_date()
    seen_permissions = [(r.name, r.description, r.created_on) for r in page.permission_rows]
    assert seen_permissions == list(reversed(expected_permissions))


def test_list_pagination(async_server, browser, permissions, session):  # noqa: F811
    # type: (str, Chrome, Dict[str, Permission], Session) -> None
    """Test pagination.

    This forces the pagination to specific values, rather than using the page controls, since we
    don't create more than 100 permissions for testing.
    """
    settings.override_timezone("UTC")
    fe_url = url(async_server, "/permissions?limit=1&offset=1")
    browser.get(fe_url)
    page = PermissionsPage(browser)
    seen_permissions = [(r.name, r.description, r.created_on) for r in page.permission_rows]
    expected_permissions = [
        (p.name, p.description, print_date(p.created_on)) for p in permissions.values()
    ]
    assert seen_permissions == sorted(expected_permissions)[1:2]


def test_create_button(async_server, browser, groups, session):  # noqa: F811
    # type: (str, Chrome, Dict[str, Group], Session) -> None
    fe_url = url(async_server, "/permissions")
    browser.get(fe_url)
    page = PermissionsPage(browser)
    assert not page.has_create_permission_button

    # Now grant the permission to manage permissions to a group the test user is a member of.
    group = groups["permission-admins"]
    permission = create_permission(session, PERMISSION_CREATE)
    session.commit()
    grant_permission(session, group.id, permission.id, argument="*")

    # Request the list again with a graph refresh and check that the button exists.
    fe_url = url(async_server, "/permissions?refresh=yes")
    browser.get(fe_url)
    assert page.has_create_permission_button
