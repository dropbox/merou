from typing import TYPE_CHECKING

from grouper.constants import USER_ADMIN
from itests.pages.groups import GroupViewPage
from itests.pages.service_accounts import (
    ServiceAccountCreatePage,
    ServiceAccountEnablePage,
    ServiceAccountGrantPermissionPage,
    ServiceAccountViewPage,
)
from itests.pages.users import UsersViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py.path import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_service_account_lifecycle(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
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


def test_create_duplicate(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
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


def test_permission_grant_revoke(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
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


def test_permission_grant_denied(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.grant_permission_to_group("some-permission", "foo", "some-group")
        setup.create_service_account("service@svc.localhost", "some-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/service/service@svc.localhost/grant"))

        page = ServiceAccountGrantPermissionPage(browser)
        page.select_permission("some-permission (foo)")
        page.set_argument("bar")
        page.submit()

        assert page.has_alert("The group some-group does not have that permission")


def test_permission_grant_invalid_argument(tmpdir, setup, browser):
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

        print(page.root.page_source)
        assert page.has_alert("argument")
