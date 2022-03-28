from typing import TYPE_CHECKING

import pytest
from selenium.common.exceptions import NoSuchElementException

from grouper.entities.group import GroupJoinPolicy
from itests.pages.groups import GroupsViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_list_groups(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_group("one-group", "Some group", GroupJoinPolicy.CAN_JOIN)
        setup.create_group("another-group", "Another group", GroupJoinPolicy.CAN_ASK)
        setup.create_group("private", join_policy=GroupJoinPolicy.NOBODY)

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups"))
        page = GroupsViewPage(browser)

        group_row = page.find_group_row("one-group")
        assert group_row.name == "one-group"
        assert group_row.href == url(frontend_url, "/groups/one-group")
        assert group_row.description == "Some group"
        assert group_row.can_join == "Anyone"

        group_row = page.find_group_row("another-group")
        assert group_row.name == "another-group"
        assert group_row.href == url(frontend_url, "/groups/another-group")
        assert group_row.description == "Another group"
        assert group_row.can_join == "Must Ask"

        group_row = page.find_group_row("private")
        assert group_row.name == "private"
        assert group_row.href == url(frontend_url, "/groups/private")
        assert group_row.description == ""
        assert group_row.can_join == "Nobody"


def test_list_audited_groups(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_group("one-group", "Some group")
        setup.create_group("audited-group", "Another group")
        setup.create_permission("audited", "", audited=True)
        setup.grant_permission_to_group("audited", "", "audited-group")
        setup.add_group_to_group("child-audited", "audited-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups"))
        page = GroupsViewPage(browser)
        assert page.find_group_row("one-group")
        assert page.find_group_row("audited-group")
        assert page.find_group_row("child-audited")

        page.click_show_audited_button()
        row = page.find_group_row("audited-group")
        assert row.audited_reason == "Direct"
        row = page.find_group_row("child-audited")
        assert row.audited_reason == "Inherited"
        with pytest.raises(NoSuchElementException):
            page.find_group_row("one-group")
