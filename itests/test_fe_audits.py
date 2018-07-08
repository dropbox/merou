from datetime import datetime, timedelta

from fixtures import async_server, browser  # noqa: F401
from pages.audits import AuditsCreatePage
from pages.groups import GroupViewPage
from plugins import group_ownership_policy
from tests.fixtures import graph, groups, service_accounts, permissions, session, standard_graph, users  # noqa: F401
from tests.fixtures import fe_app as app  # noqa: F401
from tests.url_util import url
from tests.util import add_member


def test_remove_last_owner_via_audit(async_server, browser, users, groups, session):  # noqa: F811
    future = datetime.utcnow() + timedelta(1)

    add_member(groups["auditors"], users["cbguder@a.co"], role="owner")
    add_member(groups["audited-team"], users["cbguder@a.co"], role="owner", expiration=future)

    session.commit()

    fe_url = url(async_server, "/audits/create")
    browser.get(fe_url)

    page = AuditsCreatePage(browser)

    page.set_end_date(future.strftime("%m/%d/%Y"))
    page.submit()

    fe_url = url(async_server, "/groups/audited-team")
    browser.get(fe_url)

    page = GroupViewPage(browser)

    audit_modal = page.get_audit_modal()
    audit_modal.find_member_row("zorkian@a.co").set_audit_status("remove")
    audit_modal.confirm()

    assert page.current_url.endswith("/groups/audited-team")
    assert page.has_text(group_ownership_policy.EXCEPTION_MESSAGE)
