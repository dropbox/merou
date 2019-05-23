from typing import TYPE_CHECKING

from grouper.entities.group import GroupJoinPolicy
from itests.pages.groups import GroupJoinPage, GroupsViewPage, GroupViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py.path import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_require_clickthru(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups"))
        groups_page = GroupsViewPage(browser)

        groups_page.click_create_group_button()
        create_group_modal = groups_page.get_create_group_modal()
        create_group_modal.set_group_name("test-group")
        create_group_modal.set_join_policy(GroupJoinPolicy.CAN_JOIN)
        create_group_modal.click_require_clickthru_checkbox()
        create_group_modal.confirm()

    with frontend_server(tmpdir, "rra@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/test-group/join"))
        join_page = GroupJoinPage(browser)

        join_page.set_reason("Testing")
        join_page.submit()
        clickthru_modal = join_page.get_clickthru_modal()
        clickthru_modal.confirm()

        group_page = GroupViewPage(browser)
        assert group_page.current_url.endswith("/groups/test-group?refresh=yes")
        assert group_page.find_member_row("rra@a.co")
