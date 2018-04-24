from pages.groups import GroupViewPage
from pages.service_accounts import (
    ServiceAccountCreatePage,
    ServiceAccountEnablePage,
    ServiceAccountViewPage,
)
from pages.users import UsersViewPage

from fixtures import async_server, browser  # noqa: F401
from tests.fixtures import graph, groups, permissions, session, standard_graph, users  # noqa: F401
from tests.url_util import url


def test_service_account_lifecycle(async_server, browser):  # noqa: F811
    browser.get(url(async_server, "/groups/team-sre"))

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
    page.select_owner("Group: team-sre")
    page.submit()
