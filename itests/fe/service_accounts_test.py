from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from selenium.common.exceptions import NoSuchElementException

from grouper.constants import PERMISSION_ADMIN, USER_ADMIN
from itests.pages.base import BasePage
from itests.pages.error import ErrorPage
from itests.pages.groups import GroupViewPage
from itests.pages.service_accounts import (
    ServiceAccountCreatePage,
    ServiceAccountEditPage,
    ServiceAccountEnablePage,
    ServiceAccountGrantPermissionPage,
    ServiceAccountViewPage,
)
from itests.pages.users import UsersViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_service_account_lifecycle(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("cbguder@a.co", "user-admins")
        setup.add_user_to_group("cbguder@a.co", "some-group")
        setup.grant_permission_to_group(USER_ADMIN, "", "user-admins")

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/user-admins"))

        group_page = GroupViewPage(browser)
        group_page.click_add_service_account_button()

        # Test with an invalid machine set.
        create_page = ServiceAccountCreatePage(browser)
        create_page.set_name("my-special-service-account")
        create_page.set_description("some description")
        create_page.set_machine_set("some machines bad-machine")
        create_page.submit()
        assert create_page.has_alert("machine_set")
        expected = "my-special-service-account@svc.localhost has invalid machine set"
        assert create_page.has_alert(expected)

        # Fix the machine set but test with an invalid name.
        create_page.set_name("service@service@service")
        create_page.set_machine_set("some machines")
        create_page.submit()
        assert create_page.has_alert("name")

        # Fix the name and then creation should succeed.
        create_page.set_name("my-special-service-account")
        create_page.submit()

        view_page = ServiceAccountViewPage(browser)
        assert view_page.owner == "user-admins"
        assert view_page.description == "some description"
        assert view_page.machine_set == "some machines"
        view_page.click_disable_button()
        disable_modal = view_page.get_disable_modal()
        disable_modal.confirm()

        browser.get(url(frontend_url, "/users"))

        users_page = UsersViewPage(browser)
        users_page.click_show_disabled_users_button()
        users_page.click_show_service_accounts_button()
        user_row = users_page.find_user_row("my-special-service-account@svc.localhost (service)")
        user_row.click()

        view_page = ServiceAccountViewPage(browser)
        view_page.click_enable_button()

        enable_page = ServiceAccountEnablePage(browser)
        enable_page.select_owner("Group: some-group")
        enable_page.submit()

        view_page = ServiceAccountViewPage(browser)
        assert view_page.owner == "some-group"


def test_service_account_edit(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("cbguder@a.co", "some-group")
        setup.create_service_account("service@svc.localhost", "some-group")

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service@svc.localhost"))

        view_page = ServiceAccountViewPage(browser)
        assert view_page.owner == "some-group"
        assert view_page.description == ""
        assert view_page.machine_set == ""
        view_page.click_edit_button()

        edit_page = ServiceAccountEditPage(browser)
        edit_page.set_description("some description")
        edit_page.set_machine_set("some machines bad-machine")
        edit_page.submit()
        assert edit_page.has_alert("machine_set")
        assert edit_page.has_alert("service@svc.localhost has invalid machine set")

        edit_page.set_machine_set("some machines")
        edit_page.submit()

        assert browser.current_url.endswith("/groups/some-group/service/service@svc.localhost")
        assert view_page.description == "some description"
        assert view_page.machine_set == "some machines"


def test_wrong_owner(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.create_group("other-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/other-group/service/service@svc.localhost"))
        page = BasePage(browser)
        assert page.subheading == "404 Not Found"
        assert page.has_text("whatever you were looking for wasn't found")


def test_escaped_at_sign(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.create_service_account("service@svc.localhost", "some-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service%40svc.localhost"))
        page = ServiceAccountViewPage(browser)
        assert page.subheading == "Service Account: service@svc.localhost"
        assert page.owner == "some-group"


def test_create_duplicate(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("cbguder@a.co", "some-group")
        setup.create_service_account("service@svc.localhost", "some-group")

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/create"))
        page = ServiceAccountCreatePage(browser)
        page.set_name("service")
        page.submit()
        assert page.has_alert("name")
        assert page.has_alert("service account with name service@svc.localhost already exists")


def test_permission_grant(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.add_user_to_group("rra@a.co", "other-group")
        setup.add_user_to_group("cbguder@a.co", "permission-admins")
        setup.grant_permission_to_group("some-permission", "foo", "some-group")
        setup.grant_permission_to_group(
            "grouper.permission.grant", "some-permission/bar", "other-group"
        )
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "permission-admins")
        setup.create_service_account("service@svc.localhost", "some-group")

    # Member of the owning group should be able to delegate perms down from the owning group
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service@svc.localhost"))

        page = ServiceAccountViewPage(browser)
        assert page.permission_rows == []
        page.click_add_permission_button()

        grant_page = ServiceAccountGrantPermissionPage(browser)
        grant_page.select_permission("some-permission (foo)")
        grant_page.set_argument("foo")
        grant_page.submit()

        permission_rows = page.permission_rows
        assert len(permission_rows) == 1
        permission = permission_rows[0]
        assert permission.permission == "some-permission"
        assert permission.argument == "foo"

    # Unrelated user can grant perms for which they have the appropriate grouper.permission.grant
    with frontend_server(tmpdir, "rra@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service@svc.localhost"))

        page = ServiceAccountViewPage(browser)
        assert len(page.permission_rows) == 1
        page.click_add_permission_button()

        grant_page = ServiceAccountGrantPermissionPage(browser)
        grant_page.select_permission("some-permission (bar)")
        grant_page.set_argument("bar")
        grant_page.submit()

        permission_rows = page.permission_rows
        assert len(permission_rows) == 2
        permission = permission_rows[1]
        assert permission.permission == "some-permission"
        assert permission.argument == "bar"

    # Permission admin can grant any permission with any argument to any service account
    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service@svc.localhost"))

        page = ServiceAccountViewPage(browser)
        assert len(page.permission_rows) == 2
        page.click_add_permission_button()

        grant_page = ServiceAccountGrantPermissionPage(browser)
        grant_page.select_permission("some-permission (*)")
        grant_page.set_argument("weewoo")
        grant_page.submit()

        permission_rows = page.permission_rows
        assert len(permission_rows) == 3
        permission = permission_rows[2]
        assert permission.permission == "some-permission"
        assert permission.argument == "weewoo"


def test_permission_grant_revoke(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.grant_permission_to_group("some-permission", "foo", "some-group")
        setup.grant_permission_to_group("other-permission", "bar", "parent-group")
        setup.add_group_to_group("some-group", "parent-group")
        setup.create_service_account("service@svc.localhost", "some-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service@svc.localhost"))

        page = ServiceAccountViewPage(browser)
        assert page.owner == "some-group"
        assert page.permission_rows == []
        page.click_add_permission_button()

        grant_page = ServiceAccountGrantPermissionPage(browser)
        grant_page.select_permission("some-permission (foo)")
        grant_page.set_argument("foo")
        grant_page.submit()

        assert page.owner == "some-group"
        permission_rows = page.permission_rows
        assert len(permission_rows) == 1
        permission = permission_rows[0]
        assert permission.permission == "some-permission"
        assert permission.argument == "foo"

        permission.click_revoke_button()
        permission_revoke_modal = page.get_revoke_permission_modal()
        permission_revoke_modal.confirm()

        assert page.owner == "some-group"
        assert page.permission_rows == []

        # Add a permission from the parent group.
        page.click_add_permission_button()

        grant_page = ServiceAccountGrantPermissionPage(browser)
        grant_page.select_permission("other-permission (bar)")
        grant_page.set_argument("bar")
        grant_page.submit()

        permission_rows = page.permission_rows
        assert len(permission_rows) == 1
        permission = permission_rows[0]
        assert permission.permission == "other-permission"
        assert permission.argument == "bar"


def test_permission_grant_denied(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.add_user_to_group("rra@a.co", "other-group")
        setup.grant_permission_to_group("some-permission", "foo", "some-group")
        setup.create_service_account("service@svc.localhost", "some-group")

    # Member of the owning team will get denied when trying to grant a perm the team doesn't have
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service@svc.localhost/grant"))

        page = ServiceAccountGrantPermissionPage(browser)
        page.select_permission("some-permission (foo)")
        page.set_argument("bar")
        page.submit()

        assert page.has_alert("Permission denied")

    # Unrelated user can click the Add Permission button but will get a 403
    with frontend_server(tmpdir, "rra@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service@svc.localhost"))

        view_page = ServiceAccountViewPage(browser)
        assert len(view_page.permission_rows) == 0
        view_page.click_add_permission_button()

        forbidden_page = ErrorPage(browser)
        assert forbidden_page.heading == "Error"
        assert forbidden_page.subheading == "403 Forbidden"


def test_permission_grant_invalid_argument(
    tmpdir: LocalPath, setup: SetupTest, browser: Chrome
) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.grant_permission_to_group("some-permission", "foo", "some-group")
        setup.create_service_account("service@svc.localhost", "some-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service@svc.localhost/grant"))

        page = ServiceAccountGrantPermissionPage(browser)
        page.select_permission("some-permission (foo)")
        page.set_argument("@@@@")
        page.submit()

        assert page.has_alert("argument")


def test_permission_revoke_denied(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.grant_permission_to_service_account("some-permission", "*", "service@svc.localhost")
        setup.create_user("gary@a.co")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service@svc.localhost"))

        page = ServiceAccountViewPage(browser)
        assert page.owner == "some-group"
        permission_rows = page.permission_rows
        assert len(permission_rows) == 1
        permission = permission_rows[0]
        assert permission.permission == "some-permission"
        assert permission.argument == "*"

        # The button doesn't show for someone who can't manage the service account.
        with pytest.raises(NoSuchElementException):
            permission.click_revoke_button()

    # Add the user to the group so that the revoke button will show up, and then revoke it before
    # attempting to click the button.  We can't just directly initiate a request to the revoke URL
    # without making the button appear because Python Selenium doesn't support a test-initiated
    # POST (only GET).
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service@svc.localhost"))

        page = ServiceAccountViewPage(browser)
        assert page.owner == "some-group"
        permission_rows = page.permission_rows
        assert len(permission_rows) == 1
        permission = permission_rows[0]

        with setup.transaction():
            setup.remove_user_from_group("gary@a.co", "some-group")

        permission.click_revoke_button()
        permission_revoke_modal = page.get_revoke_permission_modal()
        permission_revoke_modal.confirm()

        assert page.has_text("The operation you tried to complete is unauthorized")
