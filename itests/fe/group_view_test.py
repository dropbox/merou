from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from mock import ANY
from selenium.common.exceptions import NoSuchElementException

from grouper.constants import GROUP_ADMIN, PERMISSION_GRANT
from grouper.entities.permission_grant import GroupPermissionGrant
from itests.pages.groups import (
    GroupEditMemberPage,
    GroupEditPage,
    GroupViewPage,
    PermissionGrantPage,
)
from itests.pages.permission_request import PermissionRequestPage
from itests.pages.permission_requests import PermissionRequestUpdatePage
from itests.setup import frontend_server
from plugins import group_ownership_policy
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_show_group(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
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


def test_show_group_hides_aliased_permissions(
    tmpdir: LocalPath, setup: SetupTest, browser: Chrome
) -> None:
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


def test_rename(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))

        view_page = GroupViewPage(browser)
        view_page.click_edit_button()

        edit_page = GroupEditPage(browser)
        edit_page.set_name("other-group")
        edit_page.submit()

        assert browser.current_url.endswith("?refresh=yes")
        assert view_page.subheading == "other-group"


def test_rename_name_conflict(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")
        setup.create_group("other-group")
        setup.disable_group("other-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))

        view_page = GroupViewPage(browser)
        view_page.click_edit_button()

        edit_page = GroupEditPage(browser)
        edit_page.set_name("other-group")
        edit_page.submit()
        assert edit_page.has_alert("A group named 'other-group' already exists")


def test_remove_member(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
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


def test_remove_last_owner(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
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


def test_grant_permission(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.grant_permission_to_group(PERMISSION_GRANT, "some-permission", "some-group")
        setup.create_permission("some-permission")
        setup.create_group("other-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))

        group_page = GroupViewPage(browser)
        assert group_page.find_permission_rows("some-permission") == []
        group_page.click_add_permission_button()

        grant_page = PermissionGrantPage(browser)
        grant_page.set_permission("some-permission")
        grant_page.set_argument("foo")
        grant_page.submit()

        rows = group_page.find_permission_rows("some-permission")
        assert len(rows) == 1
        assert rows[0].argument == "foo"

        # Grant a permission with surrounding and internal whitespace to test whitespace handling.
        browser.get(url(frontend_url, "/groups/other-group"))
        assert group_page.find_permission_rows("some-permission") == []
        group_page.click_add_permission_button()

        grant_page.set_permission("some-permission")
        grant_page.set_argument("  arg u  ment  ")
        grant_page.submit()

        rows = group_page.find_permission_rows("some-permission")
        assert len(rows) == 1
        assert rows[0].argument in ("arg u ment", "arg u  ment")  # browser messes with whitespace

    # Check directly in the database to make sure the whitespace is stripped, since we may not be
    # able to see it via the browser.  We need to explicitly reopen the database since otherwise
    # SQLite doesn't always see changes written by the frontend.
    setup.reopen_database()
    permission_grant_repository = setup.sql_repository_factory.create_permission_grant_repository()
    grants = permission_grant_repository.permission_grants_for_group("other-group")
    assert grants == [
        GroupPermissionGrant(
            group="other-group",
            permission="some-permission",
            argument="arg u  ment",
            granted_on=ANY,
            is_alias=False,
            grant_id=ANY,
        )
    ]


def test_request_permission(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", "owner")
        setup.create_permission("some-permission")
        setup.add_user_to_group("zorkian@a.co", "admins")
        setup.grant_permission_to_group(PERMISSION_GRANT, "some-permission", "admins")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))

        group_page = GroupViewPage(browser)
        group_page.click_request_permission_button()

        request_page = PermissionRequestPage(browser)
        request_page.set_permission("some-permission")
        request_page.set_argument_freeform("some-argument")
        request_page.set_reason("testing")
        request_page.submit()

        assert browser.current_url.endswith("/permissions/requests/1")
        update_page = PermissionRequestUpdatePage(browser)
        assert update_page.has_text("some-group")
        assert update_page.has_text("some-argument")
        assert update_page.has_text("testing")
