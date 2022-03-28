from typing import TYPE_CHECKING

from grouper.constants import AUDIT_MANAGER, PERMISSION_ADMIN
from itests.pages.permission_view import PermissionViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_view(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_permission("audited-permission", "", audited=True)
        setup.create_permission("some-permission", "Some permission")
        setup.create_permission("disabled-permission", "", enabled=False)
        setup.grant_permission_to_group("some-permission", "", "another-group")
        setup.grant_permission_to_group("some-permission", "foo", "some-group")
        setup.create_service_account("service@svc.localhost", "owner-group")
        setup.grant_permission_to_service_account(
            "audited-permission", "argument", "service@svc.localhost"
        )

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/some-permission/groups"))
        page = PermissionViewPage(browser)
        assert page.subheading == "some-permission 2 grant(s)"
        assert page.description == "Some permission"
        assert not page.has_disable_permission_button
        assert not page.has_disable_auditing_button
        assert not page.has_enable_auditing_button
        assert not page.has_audited_warning
        assert not page.has_disabled_warning
        grants = [(r.group, r.argument) for r in page.group_permission_grant_rows]
        assert grants == [("another-group", "(unargumented)"), ("some-group", "foo")]

        browser.get(url(frontend_url, "/permissions/some-permission/service_accounts"))
        page = PermissionViewPage(browser)
        assert page.has_no_service_account_grants

        browser.get(url(frontend_url, "/permissions/audited-permission/groups"))
        page = PermissionViewPage(browser)
        assert page.subheading == "audited-permission 0 grant(s)"
        assert not page.description
        assert page.has_audited_warning
        assert not page.has_disable_auditing_button
        assert not page.has_enable_auditing_button
        assert page.has_no_group_grants

        browser.get(url(frontend_url, "/permissions/audited-permission/service_accounts"))
        page = PermissionViewPage(browser)
        grants = [
            (r.service_account, r.argument) for r in page.service_account_permission_grant_rows
        ]
        assert grants == [("service@svc.localhost", "argument")]

        browser.get(url(frontend_url, "/permissions/disabled-permission"))
        page = PermissionViewPage(browser)
        assert page.subheading == "disabled-permission"
        assert not page.has_disable_permission_button
        assert page.has_disabled_warning


def test_view_change_audited(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "audit-managers")
        setup.grant_permission_to_group(AUDIT_MANAGER, "", "audit-managers")
        setup.create_permission("some-permission", "Some permission")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/some-permission"))
        page = PermissionViewPage(browser)
        assert not page.has_disable_permission_button
        assert not page.has_audited_warning
        assert page.has_enable_auditing_button

        page.click_enable_auditing_button()
        enable_auditing_modal = page.get_enable_auditing_modal()
        enable_auditing_modal.confirm()

        assert page.subheading == "some-permission"
        assert page.has_audited_warning
        assert not page.has_enable_auditing_button
        assert page.has_disable_auditing_button

        page.click_disable_auditing_button()
        disable_auditing_modal = page.get_disable_auditing_modal()
        disable_auditing_modal.confirm()

        assert page.subheading == "some-permission"
        assert not page.has_audited_warning
        assert page.has_enable_auditing_button
        assert not page.has_disable_auditing_button


def test_view_disable(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "administrators")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "administrators")
        setup.create_permission("some-permission", "Some permission")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/some-permission"))
        page = PermissionViewPage(browser)
        assert page.has_disable_permission_button

        page.click_disable_permission_button()
        disable_permission_modal = page.get_disable_permission_modal()
        disable_permission_modal.confirm()

        assert page.subheading == "some-permission"
        assert page.has_disabled_warning
        assert not page.has_disable_permission_button


def test_view_disable_with_grants(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "administrators")
        setup.grant_permission_to_group(PERMISSION_ADMIN, "", "administrators")
        setup.grant_permission_to_group("some-permission", "argument", "some-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/some-permission"))
        page = PermissionViewPage(browser)
        assert page.has_disable_permission_button

        page.click_disable_permission_button()
        disable_permission_modal = page.get_disable_permission_modal()
        disable_permission_modal.confirm()

        assert page.has_alert("cannot be disabled while it is still granted")
        assert not page.has_disabled_warning
        assert page.has_disable_permission_button
