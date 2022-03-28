from typing import TYPE_CHECKING

from itests.pages.error import ErrorPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_invalid_user(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with frontend_server(tmpdir, "has.period@a.co") as frontend_url:
        browser.get(url(frontend_url, "/"))
        page = ErrorPage(browser)
        assert page.heading == "Error"
        assert page.subheading == "403 Forbidden"
        assert "has.period@a.co does not match" in page.content


def test_service_account(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_service_account("service@svc.localhost", "some-group")

    with frontend_server(tmpdir, "service@svc.localhost") as frontend_url:
        browser.get(url(frontend_url, "/"))
        page = ErrorPage(browser)
        assert page.heading == "Error"
        assert page.subheading == "403 Forbidden"
        assert "service@svc.localhost is a service account" in page.content


def test_disabled_user(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None
    with setup.transaction():
        setup.create_user("disabled@a.co")
        setup.session.flush()
        setup.disable_user("disabled@a.co")

    with frontend_server(tmpdir, "disabled@a.co") as frontend_url:
        browser.get(url(frontend_url, "/"))
        page = ErrorPage(browser)
        assert page.heading == "Error"
        assert page.subheading == "403 Forbidden"
        assert "disabled@a.co is not an active account" in page.content
