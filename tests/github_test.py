from urllib.parse import urlencode

import pytest

from grouper.constants import USER_METADATA_GITHUB_USERNAME_KEY
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.user_metadata import get_user_metadata_by_key
from tests.fixtures import (  # noqa: F401
    fe_app as app,
    graph,
    groups,
    permissions,
    service_accounts,
    session,
    standard_graph,
    users,
)
from tests.url_util import url


@pytest.mark.gen_test
def test_github(session, users, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]
    assert get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY) is None

    user = User.get(session, name=user.username)
    fe_url = url(base_url, "/users/{}/github".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"username": "joe-on-github"}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200
    user = User.get(session, name=user.username)
    assert (
        get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY) is not None
    )
    assert (
        get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY).data_value
        == "joe-on-github"
    )

    audit_entries = AuditLog.get_entries(
        session, on_user_id=user.id, action="changed_github_username"
    )
    assert len(audit_entries) == 1
    assert audit_entries[0].description == "Changed GitHub username: joe-on-github"

    fe_url = url(base_url, "/users/{}/github".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"username": ""}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200
    user = User.get(session, name=user.username)
    assert get_user_metadata_by_key(session, user.id, USER_METADATA_GITHUB_USERNAME_KEY) is None
