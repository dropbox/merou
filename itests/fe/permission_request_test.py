import time
from typing import TYPE_CHECKING

from mock import ANY

from grouper.constants import PERMISSION_GRANT
from grouper.entities.permission_grant import GroupPermissionGrant
from itests.pages.groups import GroupViewPage
from itests.pages.permission import PermissionPage
from itests.pages.permission_request import PermissionRequestPage
from itests.pages.permission_requests import PermissionRequestsPage, PermissionRequestUpdatePage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_requesting_permission(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_group("dev-infra")
        setup.create_group("front-end")
        setup.create_permission(name="git.repo.read")
        setup.create_user("brhodes@a.co")

        setup.add_user_to_group("brhodes@a.co", "front-end")
        setup.grant_permission_to_group(PERMISSION_GRANT, "git.repo.read", "dev-infra")

    with frontend_server(tmpdir, "brhodes@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/git.repo.read"))

        page1 = PermissionPage(browser)
        assert page1.heading == "Permissions"
        assert page1.subheading == "git.repo.read"
        page1.button_to_request_this_permission.click()

        page2 = PermissionRequestPage(browser)
        assert page2.heading == "Permissions"
        assert page2.subheading == "Request Permission"
        assert page2.get_group_values() == ["", "front-end"]
        assert page2.get_permission_values() == ["git.repo.read"]

        page2.set_group("front-end")
        page2.set_argument_freeform("server")
        page2.set_reason("So they can do development")
        page2.submit()

        text = " ".join(browser.find_element_by_tag_name("body").text.split())
        assert browser.current_url.endswith("/permissions/requests/1")
        assert "brhodes@a.co pending" in text
        assert (
            "Group: front-end Permission: git.repo.read Argument: server "
            "Reason: So they can do development Waiting for approval" in text
        )


def test_unargumented_request(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_permission("sample.permission")
        setup.create_group("grouper-administrators")
        setup.add_user_to_group("gary@a.co", "grouper-administrators")
        setup.add_user_to_group("rra@a.co", "test-group")

        setup.grant_permission_to_group(
            PERMISSION_GRANT, "sample.permission", "grouper-administators"
        )

    with frontend_server(tmpdir, "rra@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/request?permission=sample.permission"))
        page = PermissionRequestPage(browser)

        page.set_group("test-group")
        page.set_argument_freeform("")
        page.set_reason("Some testing reason")
        page.submit()

        assert browser.current_url.endswith("/permissions/requests/1")


def test_limited_arguments(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_permission("sample.permission")
        setup.create_group("grouper-administrators")
        setup.add_user_to_group("gary@a.co", "grouper-administrators")
        setup.add_user_to_group("rra@a.co", "test-group")

    with frontend_server(tmpdir, "rra@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/request?permission=sample.permission"))
        page = PermissionRequestPage(browser)

        page.set_group("test-group")
        page.set_argument_dropdown("Option A")
        page.set_reason("Some testing reason")
        page.submit()

        assert browser.current_url.endswith("/permissions/requests/1")


def test_end_to_end_whitespace_in_argument(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_group("some-group")
        setup.create_permission("some-permission")
        setup.add_user_to_group("gary@a.co", "some-group", "owner")
        setup.add_user_to_group("zorkian@a.co", "admins")
        setup.grant_permission_to_group(PERMISSION_GRANT, "some-permission", "admins")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/some-permission"))

        permission_page = PermissionPage(browser)
        assert permission_page.subheading == "some-permission"
        permission_page.button_to_request_this_permission.click()

        permission_request_page = PermissionRequestPage(browser)
        permission_request_page.set_group("some-group")
        permission_request_page.set_argument_freeform("  arg u  ment  ")
        permission_request_page.set_reason("testing whitespace")
        permission_request_page.submit()
        time.sleep(0.5)  # Ensure submit() goes through before FE server shut down

    with frontend_server(tmpdir, "zorkian@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/requests?status=pending"))

        requests_page = PermissionRequestsPage(browser)
        request_rows = requests_page.request_rows
        assert len(request_rows) == 1
        request = request_rows[0]
        request.click_modify_link()

        modify_page = PermissionRequestUpdatePage(browser)
        modify_page.set_status("actioned")
        modify_page.set_reason("testing whitespace")
        modify_page.submit()

        browser.get(url(frontend_url, "/groups/some-group?refresh=yes"))
        group_page = GroupViewPage(browser)
        permission_rows = group_page.find_permission_rows("some-permission")
        assert len(permission_rows) == 1
        grant = permission_rows[0]
        assert grant.name == "some-permission"
        assert grant.argument in ("arg u ment", "arg u  ment")  # browser messes with whitespace
        assert grant.source == "(direct)"

    # Check directly in the database to make sure the whitespace is stripped, since we may not be
    # able to see it via the browser.  We need to explicitly reopen the database since otherwise
    # SQLite doesn't always see changes written by the frontend.
    setup.reopen_database()
    permission_grant_repository = setup.sql_repository_factory.create_permission_grant_repository()
    grants = permission_grant_repository.permission_grants_for_group("some-group")
    assert grants == [
        GroupPermissionGrant(
            group="some-group",
            permission="some-permission",
            argument="arg u  ment",
            granted_on=ANY,
            is_alias=False,
            grant_id=ANY,
        )
    ]
