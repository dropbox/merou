from typing import TYPE_CHECKING

from grouper.models.permission import Permission
from grouper.models.permission_request import PermissionRequest
from grouper.models.permission_request_status_change import PermissionRequestStatusChange
from itests.pages.permission import PermissionPage
from itests.pages.permission_request import PermissionRequestPage
from itests.setup import frontend_server
from tests.url_util import url

if TYPE_CHECKING:
    from py.path import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_requesting_permission(tmpdir, setup, browser):
    # type: (LocalPath, SetupTest, Chrome) -> None

    with setup.transaction():
        setup.create_group("dev-infra")
        setup.create_group("front-end")
        setup.create_permission(name="git.repo.read")
        setup.create_user("brhodes@a.co")

        setup.add_user_to_group("brhodes@a.co", "front-end")
        setup.grant_permission_to_group("grouper.permission.grant", "git.repo.read", "dev-infra")

    with frontend_server(tmpdir, "brhodes@a.co") as frontend_url:
        browser.get(url(frontend_url, "/permissions/git.repo.read"))

        page1 = PermissionPage(browser)
        assert page1.heading == "Permissions"
        assert page1.subheading == "git.repo.read"
        page1.button_to_request_this_permission.click()

        page2 = PermissionRequestPage(browser)
        assert page2.heading == "Permissions"
        assert page2.subheading == "Request Permission"
        assert page2.get_option_values("group_name") == [u'', u'front-end']
        assert page2.get_option_values("permission_name") == [u'git.repo.read']

        page2.set_select_value("group_name", "front-end")
        page2.fill_field('argument', 'server')
        page2.fill_field('reason', 'So they can do development')
        page2.submit_request()

        text = ' '.join(browser.find_element_by_tag_name('body').text.split())
        assert browser.current_url.endswith('/permissions/requests/1')
        assert 'brhodes@a.co pending' in text
        assert (
            'Group: front-end Permission: git.repo.read Argument: server '
            'Reason: So they can do development Waiting for approval' in text
        )

    # TODO: the subsequent test "test_pending_inbound_requests" fails in
    # the MySQL version of the test suite if the request is not deleted.
    # Someone should at some point work out the test isolation story.
    setup.session.commit()
    p = Permission.get(setup.session, name='git.repo.read')
    r = PermissionRequest.get(setup.session, permission=p)
    h = PermissionRequestStatusChange.get(setup.session, request=r)
    h.delete(setup.session)
    r.delete(setup.session)
    p.delete(setup.session)
    setup.session.commit()
