# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from selenium.common.exceptions import NoSuchElementException

from grouper.entities.group import GroupJoinPolicy
from itests.pages.groups import GroupJoinPage, GroupRequestsPage, GroupsViewPage, GroupViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_request_to_join_group(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("zorkian@a.co", "sad-team", role="owner")
        setup.create_user("cbguder@a.co")

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/sad-team/join"))
        join_page = GroupJoinPage(browser)

        join_page.set_reason("Testing")
        join_page.set_expiration("12/31/2999")
        join_page.submit()

        browser.get(url(frontend_url, "/groups/sad-team/requests"))
        page = GroupRequestsPage(browser)

        request_row = page.find_request_row("User: cbguder@a.co")
        assert request_row.requester == "cbguder@a.co"
        assert request_row.status == "pending"
        assert request_row.expiration == "12/31/2999"
        assert request_row.role == "member"
        assert request_row.reason == "Testing"


def test_request_already_member(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")
        setup.add_group_to_group("some-group", "other-group")
        setup.add_user_to_group("gary@a.co", "other-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/other-group/join"))
        page = GroupJoinPage(browser)

        alerts = page.get_alerts()
        assert len(alerts) == 1
        assert "You and all groups" in alerts[0].text
        with pytest.raises(NoSuchElementException):
            page.set_reason("Testing")


def test_request_options(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")
        setup.create_group("other-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/other-group/join"))
        page = GroupJoinPage(browser)

        options = [o.get_attribute("value") for o in page.get_member_options()]
        assert options == ["User: gary@a.co", "Group: some-group"]

        page.set_reason("Testing")
        page.submit()

        # Now that there is a pending request, the first option should be blank and there should be
        # a notice saying that there is already a pending membership request.
        browser.get(url(frontend_url, "/groups/other-group/join"))
        options = [o.get_attribute("value") for o in page.get_member_options()]
        assert options == ["", "Group: some-group"]
        alerts = page.get_alerts()
        assert len(alerts) == 1
        assert "already a member" in alerts[0].text

        # Attempting to submit the form should fail, asking the user to select a value.
        page.set_reason("Testing")
        page.submit()
        assert page.current_url == url(frontend_url, "/groups/other-group/join")


def test_require_clickthru(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups"))
        groups_page = GroupsViewPage(browser)

        groups_page.click_create_group_button()
        create_group_modal = groups_page.get_create_group_modal()
        create_group_modal.set_group_name("test-group")
        create_group_modal.set_join_policy(GroupJoinPolicy.CAN_JOIN)
        create_group_modal.click_require_clickthru_checkbox()
        create_group_modal.confirm()
        time.sleep(0.5)  # Ensure confirm() goes through before FE server is shut down

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


def test_group_join_group(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", "owner")
        setup.create_group("parent-group", join_policy=GroupJoinPolicy.CAN_JOIN)

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/parent-group/join"))
        join_page = GroupJoinPage(browser)

        join_page.set_member("some-group")
        join_page.set_reason("Testing")
        join_page.submit()

        group_page = GroupViewPage(browser)
        assert group_page.find_member_row("some-group")


def test_group_join_as_owner(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.create_group("some-group", join_policy=GroupJoinPolicy.CAN_JOIN)

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/join"))
        join_page = GroupJoinPage(browser)

        join_page.set_role("Owner")
        join_page.set_reason("Testing")
        join_page.submit()

        view_page = GroupViewPage(browser)
        with pytest.raises(NoSuchElementException):
            view_page.find_member_row("gary@a.co")


def test_group_join_group_as_owner(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", "owner")
        setup.create_group("parent-group", join_policy=GroupJoinPolicy.CAN_JOIN)

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/parent-group/join"))
        join_page = GroupJoinPage(browser)

        join_page.set_member("some-group")
        join_page.set_reason("Testing")
        for role in ("Manager", "Owner", "Np-Owner"):
            join_page.set_role(role)
            join_page.submit()
            assert join_page.has_alert("Groups can only have the role of 'member'")


def test_request_join_unicode(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", "owner")

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group/join"))
        page = GroupJoinPage(browser)

        page.set_reason("защото причини")
        page.submit()

        assert browser.current_url.endswith("/groups/some-group?refresh=yes")
