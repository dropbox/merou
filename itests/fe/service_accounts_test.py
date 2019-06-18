from typing import TYPE_CHECKING

from itests.fixtures import async_server  # noqa: F401
from itests.pages.groups import GroupViewPage
from itests.pages.service_accounts import (
    ServiceAccountCreatePage,
    ServiceAccountEnablePage,
    ServiceAccountGrantPermissionPage,
    ServiceAccountViewPage,
)
from itests.pages.users import UsersViewPage
from itests.setup import frontend_server
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
    from py.path import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_service_account_lifecycle(async_server, browser):  # noqa: F811
    browser.get(url(async_server, "/groups/user-admins"))

    page = GroupViewPage(browser)
    page.click_add_service_account_button()

    page = ServiceAccountCreatePage(browser)
    page.set_name("my-special-service-account")
    page.submit()

    page = ServiceAccountViewPage(browser)
    page.click_disable_button()

    disable_modal = page.get_disable_modal()
    disable_modal.confirm()

    browser.get(url(async_server, "/users"))

    page = UsersViewPage(browser)
    page.click_show_disabled_users_button()
    page.click_show_service_accounts_button()

    user_row = page.find_user_row("my-special-service-account@svc.localhost (service)")
    user_row.click()

    page = ServiceAccountViewPage(browser)
    page.click_enable_button()

    page = ServiceAccountEnablePage(browser)
    page.select_owner("Group: user-admins")
    page.submit()


def test_permission_grant_revoke(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.grant_permission_to_group("some-permission", "foo", "some-group")
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
