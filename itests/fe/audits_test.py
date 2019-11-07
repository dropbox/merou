from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from grouper.constants import AUDIT_MANAGER, AUDIT_VIEWER, PERMISSION_AUDITOR
from itests.pages.audits import AuditsCreatePage
from itests.pages.groups import GroupViewPage
from itests.setup import frontend_server
from plugins import group_ownership_policy
from tests.url_util import url

if TYPE_CHECKING:
    from py.path import LocalPath
    from selenium.webdriver import Chrome
    from tests.setup import SetupTest


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
