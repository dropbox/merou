from pages.exceptions import NoSuchElementException
from pages.groups import GroupEditMemberPage, GroupsViewPage, GroupViewPage
from plugins import group_ownership_policy

import pytest

from tests.fixtures import graph, groups, permissions, session, standard_graph, users  # noqa: F401
from tests.fixtures import fe_app as app  # noqa: F401
from tests.url_util import url

from fixtures import async_server, browser  # noqa: F401


def test_list_groups(async_server, browser, groups):  # noqa: F811
    fe_url = url(async_server, "/groups")
    browser.get(fe_url)

    page = GroupsViewPage(browser)

    for name, _ in groups.iteritems():
        row = page.find_group_row(name)
        assert row.href.endswith("/groups/{}".format(name))


def test_show_group(async_server, browser, groups):  # noqa: F811
    fe_url = url(async_server, "/groups/team-sre")
    browser.get(fe_url)

    page = GroupViewPage(browser)

    members = groups["team-sre"].my_members()
    for [_, username], _ in members.iteritems():
        row = page.find_member_row(username)
        assert row.href.endswith("/users/{}".format(username))


def test_remove_member(async_server, browser):  # noqa: F811
    fe_url = url(async_server, "/groups/team-sre")
    browser.get(fe_url)

    page = GroupViewPage(browser)

    row = page.find_member_row("zorkian@a.co")
    assert row.role == "member"

    row.click_remove_button()

    modal = page.get_remove_user_modal()
    modal.confirm()

    assert page.current_url.endswith("/groups/team-sre?refresh=yes")

    with pytest.raises(NoSuchElementException):
        assert page.find_member_row("zorkian@a.co")


def test_remove_last_owner(async_server, browser):  # noqa: F811
    fe_url = url(async_server, "/groups/team-sre")
    browser.get(fe_url)

    page = GroupViewPage(browser)

    row = page.find_member_row("gary@a.co")
    assert row.role == "owner"

    row.click_remove_button()

    modal = page.get_remove_user_modal()
    modal.confirm()

    row = page.find_member_row("gary@a.co")
    assert row.role == "owner"

    assert page.has_text(group_ownership_policy.EXCEPTION_MESSAGE)


def test_expire_last_owner(async_server, browser):  # noqa: F811
    fe_url = url(async_server, "/groups/sad-team")
    browser.get(fe_url)

    page = GroupViewPage(browser)

    row = page.find_member_row("zorkian@a.co")
    row.click_edit_button()

    page = GroupEditMemberPage(browser)

    page.set_expiration("12/31/2999")
    page.set_reason("Unit Testing")
    page.submit()

    assert page.current_url.endswith("/groups/sad-team/edit/user/zorkian@a.co")
    assert page.has_text(group_ownership_policy.EXCEPTION_MESSAGE)
