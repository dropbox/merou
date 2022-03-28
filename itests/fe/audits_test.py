from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from grouper.constants import AUDIT_MANAGER, AUDIT_VIEWER, PERMISSION_AUDITOR
from grouper.models.async_notification import AsyncNotification
from grouper.models.group import Group
from itests.pages.audits import AuditsCreatePage
from itests.pages.groups import GroupViewPage
from itests.setup import frontend_server
from plugins import group_ownership_policy
from tests.url_util import url

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


def test_disabling_group_clears_audit(
    tmpdir: LocalPath, setup: SetupTest, browser: Chrome
) -> None:
    future = datetime.utcnow() + timedelta(days=60)

    with setup.transaction():
        setup.add_user_to_group("gary@a.co", "some-group", role="owner")
        setup.add_user_to_group("zorkian@a.co", "some-group")
        setup.create_permission("some-permission", audited=True)
        setup.grant_permission_to_group("some-permission", "argument", "some-group")
        setup.add_user_to_group("gary@a.co", "auditors")
        setup.grant_permission_to_group(AUDIT_VIEWER, "", "auditors")
        setup.grant_permission_to_group(AUDIT_MANAGER, "", "auditors")
        setup.grant_permission_to_group(PERMISSION_AUDITOR, "", "auditors")

    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/audits/create"))

        create_page = AuditsCreatePage(browser)
        create_page.set_end_date(future.strftime("%m/%d/%Y"))
        create_page.submit()

        browser.get(url(frontend_url, "/groups/some-group"))

        group_page = GroupViewPage(browser)
        assert group_page.subheading == "some-group AUDIT IN PROGRESS"

    # Check that this created email reminder messages to the group owner.  We have to refresh the
    # session since otherwise SQLite may not see changes.
    setup.reopen_database()
    group = Group.get(setup.session, name="some-group")
    assert group
    expected_key = f"audit-{group.id}"
    emails = setup.session.query(AsyncNotification).filter_by(sent=False, email="gary@a.co").all()
    assert len(emails) > 0
    assert all((e.key is None or e.key == expected_key for e in emails))
    assert all(("Action required: Grouper Audit" in e.subject for e in emails))

    # Now, disable the group, which should complete the audit.
    with frontend_server(tmpdir, "gary@a.co") as frontend_url:
        browser.get(url(frontend_url, "/groups/some-group"))
        page = GroupViewPage(browser)

        audit_modal = page.get_audit_modal()
        audit_modal.click_close_button()
        page.wait_until_audit_modal_clears()
        page.click_disable_button()
        modal = page.get_disable_modal()
        modal.confirm()

        assert page.subheading == "some-group (disabled)"

    # And now all of the email messages should be marked sent except the immediate one (the one
    # that wasn't created with async_send_email).
    setup.reopen_database()
    emails = setup.session.query(AsyncNotification).filter_by(sent=False, email="gary@a.co").all()
    assert len(emails) == 1
    assert emails[0].key is None


def test_remove_last_owner_via_audit(tmpdir: LocalPath, setup: SetupTest, browser: Chrome) -> None:
    future = datetime.utcnow() + timedelta(1)

    with setup.transaction():
        setup.add_user_to_group("zorkian@a.co", "audited-team", role="owner")
        setup.create_permission("audited", audited=True)
        setup.grant_permission_to_group("audited", "", "audited-team")
        setup.add_user_to_group("cbguder@a.co", "auditors")
        setup.add_user_to_group("zorkian@a.co", "auditors", role="owner")
        setup.grant_permission_to_group(AUDIT_VIEWER, "", "auditors")
        setup.grant_permission_to_group(AUDIT_MANAGER, "", "auditors")
        setup.grant_permission_to_group(PERMISSION_AUDITOR, "", "auditors")
        setup.add_user_to_group("cbguder@a.co", "audited-team", role="owner", expiration=future)

    with frontend_server(tmpdir, "cbguder@a.co") as frontend_url:
        browser.get(url(frontend_url, "/audits/create"))

        create_page = AuditsCreatePage(browser)
        create_page.set_end_date(future.strftime("%m/%d/%Y"))
        create_page.submit()

        browser.get(url(frontend_url, "/groups/audited-team"))
        group_page = GroupViewPage(browser)
        audit_modal = group_page.get_audit_modal()
        audit_modal.find_member_row("zorkian@a.co").set_audit_status("remove")
        audit_modal.confirm()

        assert group_page.current_url.endswith("/groups/audited-team")
        assert group_page.has_alert(group_ownership_policy.EXCEPTION_MESSAGE)
