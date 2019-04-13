from typing import TYPE_CHECKING

from itests.pages.permission_view import PermissionViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py.path import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_view(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_user("gary@a.co")
        setup.create_permission("audited-permission", "", audited=True)
        setup.create_permission("some-permission", "Some permission")
        setup.grant_permission_to_group("some-permission", "", "another-group")
        setup.grant_permission_to_group("some-permission", "foo", "some-group")
        setup.create_service_account("service@svc.localhost", "owner-group")
        setup.grant_permission_to_service_account(
            "audited-permission", "argument", "service@svc.localhost"
        )

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/some-permission"))
        page = PermissionViewPage(browser)
        assert page.subheading == "some-permission"
        assert page.description == "Some permission"
        assert not page.has_disable_permission_button
        assert not page.has_disable_auditing_button
        assert not page.has_enable_auditing_button
        assert not page.has_audited_warning
        grants = [(r.group, r.argument) for r in page.group_permission_grant_rows]
        assert grants == [("another-group", "(unargumented)"), ("some-group", "foo")]
        assert page.has_no_service_account_grants

        browser.get(url(frontend_url, "/permissions/audited-permission"))
        page = PermissionViewPage(browser)
        assert page.subheading == "audited-permission"
        assert not page.description
        assert page.has_audited_warning
        assert not page.has_disable_auditing_button
        assert not page.has_enable_auditing_button
        assert page.has_no_group_grants
        grants = [
            (r.service_account, r.argument) for r in page.service_account_permission_grant_rows
        ]
        assert grants == [("service@svc.localhost", "argument")]
