from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from selenium.common.exceptions import NoSuchElementException

from itests.pages.groups import GroupLeavePage, GroupViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_leave(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))

        view_page = GroupViewPage(browser)
        assert view_page.find_member_row("gary@a.co")
        view_page.click_leave_button()

        leave_page = GroupLeavePage(browser)
        assert leave_page.subheading == "Leave (some-group)"
        leave_page.submit()

        assert browser.current_url.endswith("/groups/some-group?refresh=yes")
        with pytest.raises(NoSuchElementException):
            view_page.find_member_row("gary@a.co")


def test_leave_as_owner(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")
        setup.add_user_to_group("zorkian@a.co", "some-group", role="np-owner")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))

        view_page = GroupViewPage(browser)
        assert view_page.find_member_row("gary@a.co")
        view_page.click_leave_button()

        leave_page = GroupLeavePage(browser)
        leave_page.submit()

        assert browser.current_url.endswith("/groups/some-group?refresh=yes")
        with pytest.raises(NoSuchElementException):
            view_page.find_member_row("gary@a.co")


def test_leave_as_last_owner(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")
        setup.add_user_to_group("zorkian@a.co", "some-group", role="manager")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))

        view_page = GroupViewPage(browser)
        with pytest.raises(NoSuchElementException):
            view_page.click_leave_button()
