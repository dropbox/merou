import pytest

from fixtures import graph, groups, permissions, session, standard_graph, users  # noqa: F401
from fixtures import async_server, browser  # noqa: F401
from fixtures import fe_app as app  # noqa: F401
from grouper.role_user import create_role_user
from pages import (GroupEditMemberPage, GroupViewPage, GroupsViewPage, NoSuchElementException,
    RoleUserViewPage)
from url_util import url


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

    assert page.has_text("You can't remove the last permanent owner of a group")


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
    assert page.has_text("You can't remove the last permanent owner of a group")


def test_remove_last_owner_of_service_account(async_server, browser, session, users):  # noqa: F811
    create_role_user(session, users["gary@a.co"], "service@svc.localhost", "things", "canask")

    fe_url = url(async_server, "/service/service@svc.localhost")
    browser.get(fe_url)

    page = RoleUserViewPage(browser)

    row = page.find_member_row("gary@a.co")
    row.click_remove_button()

    modal = page.get_remove_user_modal()
    modal.confirm()

    assert page.current_url.endswith("/service/service@svc.localhost")
    assert page.has_text("You can't remove the last permanent owner of a group")
