from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from selenium.common.exceptions import NoSuchElementException

from itests.pages.groups import GroupEditMemberPage, GroupViewPage
from itests.setup import frontend_server
from plugins import group_ownership_policy
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_edit_self_owner(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))

        view_page = GroupViewPage(browser)
        row = view_page.find_member_row("gary@a.co")
        assert row.role == "owner"
        row.click_edit_button()

        edit_page = GroupEditMemberPage(browser)
        edit_page.set_role("No-Permissions Owner")
        edit_page.set_reason("Testing")
        edit_page.submit()

        row = view_page.find_member_row("gary@a.co")
        assert row.role == "np-owner"


def test_self_np_owner_downgrade(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="np-owner")
        setup.add_user_to_group("zorkian@a.co", "some-group", role="owner")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/edit/user/gary@a.co"))

        page = GroupEditMemberPage(browser)
        assert sorted(page.get_role_options()) == ["member", "np-owner"]
        page.set_role("Member")
        page.set_reason("Testing")
        page.submit()

        view_page = GroupViewPage(browser)
        row = view_page.find_member_row("gary@a.co")
        assert row.role == "member"


def test_self_manager_downgrade(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="manager")
        setup.add_user_to_group("zorkian@a.co", "some-group", role="owner")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/edit/user/gary@a.co"))

        page = GroupEditMemberPage(browser)
        assert sorted(page.get_role_options()) == ["member", "manager"]
        page.set_role("Member")
        page.set_reason("Testing")
        page.submit()

        view_page = GroupViewPage(browser)
        row = view_page.find_member_row("gary@a.co")
        assert row.role == "member"


def test_remove_last_owner(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/edit/user/gary@a.co"))

        page = GroupEditMemberPage(browser)
        assert sorted(page.get_role_options()) == ["manager", "member", "np-owner", "owner"]
        page.set_role("Manager")
        page.set_reason("Testing")
        page.submit()
        assert page.subheading == "Edit Member gary@a.co in some-group"
        assert page.has_alert(group_ownership_policy.EXCEPTION_MESSAGE)


def test_edit_member_group_role(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")
        setup.add_group_to_group("other-group", "some-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))

        view_page = GroupViewPage(browser)
        row = view_page.find_member_row("other-group")
        assert row.role == "member"
        row.click_edit_button()

        edit_page = GroupEditMemberPage(browser)
        with pytest.raises(NoSuchElementException):
            edit_page.set_role("Owner")
