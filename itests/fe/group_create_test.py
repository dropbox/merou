from __future__ import annotations

from typing import TYPE_CHECKING

from itests.pages.groups import GroupCreatePage, GroupsViewPage, GroupViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_group_create(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups"))

        # First create a group from the view page with an error (an invalid name, doubling as a
        # test that @ in group names is rejected).  This should leave that page and go to the
        # dedicated group creation page with the form already set up.
        groups_page = GroupsViewPage(browser)
        groups_page.click_create_group_button()
        create_group_modal = groups_page.get_create_group_modal()
        create_group_modal.set_group_name("test-group@something")
        create_group_modal.set_description("some description")
        create_group_modal.confirm()

        create_page = GroupCreatePage(browser)
        create_page.has_alert("Group names cannot contain @")
        create_page.set_group_name("test-group")
        create_page.submit()

        view_page = GroupViewPage(browser)
        assert view_page.subheading == "test-group"

        row = view_page.find_member_row("gary@a.co")
        assert row.role == "owner"
        assert row.href.endswith("/users/gary@a.co")
