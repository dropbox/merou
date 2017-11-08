from datetime import datetime, timedelta
from urllib import urlencode

from mock import patch
import pytest

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from grouper.models.audit import Audit
from page import Page
from plugins.group_ownership_policy import GroupOwnershipPolicyPlugin
from util import add_member
from url_util import url


@pytest.mark.gen_test
def test_remove_last_owner_via_audit(session, groups, users, http_client, base_url):
    headers = {"X-Grouper-User": "cbguder@a.co"}

    future = datetime.utcnow() + timedelta(1)

    group_id = groups["audited-team"].id

    add_member(groups["auditors"], users["cbguder@a.co"], role="owner")
    add_member(groups["audited-team"], users["cbguder@a.co"], role="owner", expiration=future)

    fe_url = url(base_url, '/audits/create')
    body = {'ends_at': future.strftime('%m/%d/%Y')}
    resp = yield http_client.fetch(fe_url, method="POST", headers=headers, body=urlencode(body))
    assert resp.code == 200

    audit = session.query(Audit).filter(Audit.group_id == group_id).one()

    body = {}
    for member in audit.my_members():
        key = "audit_{}".format(member.id)

        if member.member.name == "zorkian@a.co":
            body[key] = "remove"
        else:
            body[key] = "approved"

    fe_url = url(base_url, "/audits/{}/complete".format(audit.id))

    with patch("grouper.group_member.get_plugins") as get_plugins:
        get_plugins.return_value = [GroupOwnershipPolicyPlugin()]
        resp = yield http_client.fetch(fe_url, method="POST", headers=headers, body=urlencode(body))

    assert resp.code == 200

    page = Page(resp.body)
    assert page.has_text("You can't remove the last permanent owner of a group")
