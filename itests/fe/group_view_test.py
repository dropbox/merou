from typing import TYPE_CHECKING

import pytest

from grouper.constants import GROUP_ADMIN
from itests.pages.exceptions import NoSuchElementException
from itests.pages.groups import GroupViewPage
from itests.setup import frontend_server
from plugins import group_ownership_policy
from tests.url_util import url

if TYPE_CHECKING:
    from py.path import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_show_group(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "team-sre", role="owner")
        setup.add_user_to_group("zorkian@a.co", "team-sre")
        setup.grant_permission_to_group("ssh", "*", "team-sre")
        setup.grant_permission_to_group("team-sre", "foo", "team-sre")
        setup.grant_permission_to_group("team-sre", "bar", "team-sre")

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/team-sre"))
        page = GroupViewPage(browser)

        row = page.find_member_row("gary@a.co")
        assert row.role == "owner"
        assert row.href.endswith("/users/gary@a.co")
        row = page.find_member_row("zorkian@a.co")
        assert row.role == "member"
        assert row.href.endswith("/users/zorkian@a.co")

        rows = page.find_permission_rows("ssh")
        assert len(rows) == 1
        assert rows[0].argument == "*"
        assert rows[0].href.endswith("/permissions/ssh")
        rows = page.find_permission_rows("team-sre")
        for permission_row in rows:
            assert permission_row.href.endswith("/permissions/team-sre")
        assert sorted([r.argument for r in rows]) == ["bar", "foo"]


def test_show_group_hides_aliased_permissions(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "sad-team", role="owner")
        setup.create_permission("ssh")
        setup.create_permission("sudo")
        setup.grant_permission_to_group("owner", "sad-team", "sad-team")

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/sad-team"))
        page = GroupViewPage(browser)

        assert len(page.find_permission_rows("owner", "sad-team")) == 1
        assert page.find_permission_rows("ssh", "owner=sad-team") == []
        assert page.find_permission_rows("sudo", "sad-team") == []


def test_remove_member(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "team-sre", role="owner")
        setup.add_user_to_group("zorkian@a.co", "team-sre")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/team-sre"))
        page = GroupViewPage(browser)

        row = page.find_member_row("zorkian@a.co")
        assert row.role == "member"
        row.click_remove_button()

        modal = page.get_remove_user_modal()
        modal.confirm()

        assert page.current_url.endswith("/groups/team-sre?refresh=yes")

        with pytest.raises(NoSuchElementException):
            assert page.find_member_row("zorkian@a.co")


def test_remove_last_owner(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.add_user_to_group("zorkian@a.co", "team-sre", role="owner")
        setup.add_user_to_group("gary@a.co", "admins")
        setup.grant_permission_to_group(GROUP_ADMIN, "", "admins")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/team-sre"))
        page = GroupViewPage(browser)

        row = page.find_member_row("zorkian@a.co")
        assert row.role == "owner"
        row.click_remove_button()

        modal = page.get_remove_user_modal()
        modal.confirm()

        row = page.find_member_row("zorkian@a.co")
        assert row.role == "owner"
        assert page.has_alert(group_ownership_policy.EXCEPTION_MESSAGE)
