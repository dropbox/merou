from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from selenium.common.exceptions import NoSuchElementException

from itests.pages.groups import GroupViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_disable(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))
        page = GroupViewPage(browser)

        page.click_disable_button()
        modal = page.get_disable_modal()
        modal.confirm()

        assert page.subheading == "some-group (disabled)"


def test_disable_must_be_owner(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")
        setup.add_user_to_group("cbguder@a.co", "some-group")

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))
        page = GroupViewPage(browser)

        with pytest.raises(NoSuchElementException):
            page.click_disable_button()
