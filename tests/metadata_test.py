from urllib.parse import urlencode

import pytest

from grouper.models.user import User
from grouper.settings import settings
from grouper.user_metadata import get_user_metadata_by_key, set_user_metadata
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
def test_metadata(session, users, http_client, base_url):  # noqa: F811
    settings().metadata_options = {"favorite_food": [["pizza", "pizza"], ["kale", "kale"]]}

    user = users["zorkian@a.co"]
    assert not get_user_metadata_by_key(session, user.id, "favorite_food")

    user = User.get(session, name=user.username)
    set_user_metadata(session, user.id, "favorite_food", "default")
    fe_url = url(base_url, "/users/{}/metadata/favorite_food".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"value": "pizza"}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    assert get_user_metadata_by_key(session, user.id, "favorite_food").data_value == "pizza"

    fe_url = url(base_url, "/users/{}/metadata/favorite_food".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"value": "kale"}),
        headers={"X-Grouper-User": user.username},
    )

    assert get_user_metadata_by_key(session, user.id, "favorite_food").data_value == "kale"

    fe_url = url(base_url, "/users/{}/metadata/favorite_food".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"value": "donuts"}),
        headers={"X-Grouper-User": user.username},
    )

    assert get_user_metadata_by_key(session, user.id, "favorite_food").data_value == "kale"
