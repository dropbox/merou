from typing import TYPE_CHECKING

import pytest
from selenium.common.exceptions import NoSuchElementException

from itests.pages.search_results import SearchResultsPage
from itests.pages.users import UserViewPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_search(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_group("group-some")
        setup.create_permission("awesome-permission")
        setup.create_user("some@a.co")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/"))

        page = UserViewPage(browser)
        page.search_input.send_keys("some")
        page.click_search_button()

        results_page = SearchResultsPage(browser)
        print(results_page.root.page_source)
        results = [(r.type, r.name) for r in results_page.result_rows]
        assert sorted(results) == [
            ("Group", "group-some"),
            ("Permission", "awesome-permission"),
            ("User", "some@a.co"),
        ]


def test_search_escaping(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/"))

        page = UserViewPage(browser)
        page.search_input.send_keys('SEARCH"><marquee>foo</marquee>')
        page.click_search_button()

        results_page = SearchResultsPage(browser)
        with pytest.raises(NoSuchElementException):
            results_page.find_element_by_tag_name("marquee")
