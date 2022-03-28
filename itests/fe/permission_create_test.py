from typing import TYPE_CHECKING

from grouper.constants import PERMISSION_CREATE
from itests.pages.permission_create import PermissionCreatePage
from itests.pages.permission_view import PermissionViewPage
from itests.pages.permissions import PermissionsPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_list_create_button(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions"))
        page = PermissionsPage(browser)
        assert not page.has_create_permission_button

        with setup.transaction():
            setup.grant_permission_to_group(PERMISSION_CREATE, "*", "admins")
            setup.add_user_to_group("gary@a.co", "admins")
        browser.get(url(frontend_url, "/permissions?refresh=yes"))
        assert page.has_create_permission_button


def test_create_permission(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group")
        setup.grant_permission_to_group(PERMISSION_CREATE, "foo.*", "some-group")
        setup.grant_permission_to_group(PERMISSION_CREATE, "bar.baz", "some-group")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions"))
        page = PermissionsPage(browser)
        page.click_create_permission_button()

        create_page = PermissionCreatePage(browser)
        assert create_page.allowed_patterns == ["bar.baz", "foo.*"]
        create_page.set_name("foo.bar")
        create_page.set_description("testing")
        create_page.form.submit()

        view_page = PermissionViewPage(browser)
        assert view_page.subheading == "foo.bar"
        assert view_page.description == "testing"
