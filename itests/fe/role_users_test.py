"""Role users are heavily deprecated and slated to be removed, so just sanity checks."""

from __future__ import annotations

from typing import TYPE_CHECKING

from itests.pages.role_users import RoleUserViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_disable(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.create_role_user("role@a.co")
        setup.add_user_to_group("gary@a.co", "role@a.co", role="np-owner")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/service/role@a.co"))
        page = RoleUserViewPage(browser)

        assert page.subheading == "role@a.co (service)"

        page.click_disable_button()
        modal = page.get_disable_modal()
        modal.confirm()

        assert page.subheading == "role@a.co (service) (disabled)"
