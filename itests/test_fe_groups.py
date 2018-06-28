from pages.exceptions import NoSuchElementException
from pages.groups import (
    GroupEditMemberPage,
    GroupJoinPage,
    GroupRequestsPage,
    GroupsViewPage,
    GroupViewPage,
)
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
    group = groups["team-sre"]

    fe_url = url(async_server, "/groups/{}".format(group.name))
    browser.get(fe_url)

    page = GroupViewPage(browser)

    members = group.my_members()
    for [_, username], _ in members.iteritems():
        row = page.find_member_row(username)
        assert row.href.endswith("/users/{}".format(username))

    for permission in group.my_permissions():
        rows = page.find_permission_rows(permission.name)
        assert len(rows) == 1
        assert rows[0].argument == permission.argument
        assert rows[0].href.endswith("/permissions/{}".format(permission.name))


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


def test_request_to_join_group(async_server, browser):  # noqa: F811
    fe_url = url(async_server, "/groups/sad-team/join")
    browser.get(fe_url)

    page = GroupJoinPage(browser)

    page.set_reason("Testing")
    page.set_expiration("12/31/2999")
    page.submit()

    fe_url = url(async_server, "/groups/sad-team/requests")
    browser.get(fe_url)

    page = GroupRequestsPage(browser)

    request_row = page.find_request_row("User: cbguder@a.co")
    assert request_row.requester == "cbguder@a.co"
    assert request_row.status == "pending"
    assert request_row.expiration == "12/31/2999"
    assert request_row.role == "member"
    assert request_row.reason == "Testing"


def test_show_group_hides_aliased_permissions(async_server, browser):  # noqa: F811
    fe_url = url(async_server, "/groups/sad-team")
    browser.get(fe_url)

    page = GroupViewPage(browser)

    assert len(page.find_permission_rows("owner", "sad-team")) == 1

    assert page.find_permission_rows("ssh", "owner=sad-team") == []
    assert page.find_permission_rows("sudo", "sad-team") == []
