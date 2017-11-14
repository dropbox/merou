from fixtures import graph, groups, permissions, session, standard_graph, users  # noqa: F401
from fixtures import async_server, browser  # noqa: F401
from fixtures import fe_app as app  # noqa: F401
from pages import UserViewPage
from url_util import url


def test_disable_last_owner(async_server, browser):
    fe_url = url(async_server, "/users/gary@a.co")
    browser.get(fe_url)

    page = UserViewPage(browser)

    page.click_disable_button()

    modal = page.get_disable_user_modal()
    modal.confirm()

    assert page.current_url.endswith("/users/gary@a.co")
    assert page.has_text("You can't remove the last permanent owner of a group")
