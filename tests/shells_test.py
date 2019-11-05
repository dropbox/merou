from urllib.parse import urlencode

import pytest

from grouper.constants import USER_METADATA_SHELL_KEY
from grouper.models.user import User
from grouper.settings import settings
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
def test_shell(session, users, http_client, base_url):  # noqa: F811
    settings().shell = [["/bin/bash", "bash"], ["/bin/zsh", "zsh"]]

    user = users["zorkian@a.co"]
    assert not get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY)

    user = User.get(session, name=user.username)
    fe_url = url(base_url, "/users/{}/shell".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"shell": "/bin/bash"}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    user = User.get(session, name=user.username)

    assert (
        get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY) is not None
    ), "The user should have shell metadata"
    assert (
        get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY).data_value
        == "/bin/bash"
    )

    fe_url = url(base_url, "/users/{}/shell".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"shell": "/bin/fish"}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    user = User.get(session, name=user.username)

    assert (
        get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY) is not None
    ), "The user should have shell metadata"
    assert (
        get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY).data_value
        == "/bin/bash"
    )

    fe_url = url(base_url, "/users/{}/shell".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"shell": "/bin/zsh"}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    user = User.get(session, name=user.username)

    assert (
        get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY) is not None
    ), "The user should have shell metadata"
    assert (
        get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY).data_value
        == "/bin/zsh"
    )
