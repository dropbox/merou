import time
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

import pytest
from mock import Mock, patch
from tornado.httpclient import HTTPError

from grouper.models.async_notification import AsyncNotification
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.request import Request
from grouper.models.user import User
from grouper.plugin import get_plugin_proxy
from grouper.public_key import BadPublicKey, get_public_keys_of_user
from grouper.role_user import (
    create_role_user,
    disable_role_user,
    enable_role_user,
    get_role_user,
    is_role_user,
)
from tests.constants import SSH_KEY_1, SSH_KEY_BAD, SSH_KEY_ED25519
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


def _get_unsent_and_mark_as_sent_emails_with_username(session, username):  # noqa: F811
    """Helper to count unsent emails and then mark them as sent."""
    emails = session.query(AsyncNotification).filter_by(sent=False, email=username).all()

    for email in emails:
        email.sent = True

    session.commit()
    return emails


@pytest.mark.gen_test
def test_health(session, http_client, base_url):  # noqa: F811
    health_url = url(base_url, "/debug/health")
    resp = yield http_client.fetch(health_url)
    assert resp.code == 200


@pytest.mark.gen_test
def test_auth(users, http_client, base_url):  # noqa: F811
    # no 'auth' present
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(base_url)

    # invalid user
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(base_url, headers={"X-Grouper-User": "nobody"})

    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(base_url, headers={"X-Grouper-User": "service@a.co"})

    # valid user
    resp = yield http_client.fetch(base_url, headers={"X-Grouper-User": "zorkian@a.co"})
    assert resp.code == 200


@pytest.mark.gen_test
def test_public_key(session, users, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]
    assert not get_public_keys_of_user(session, user.id)

    # add it
    fe_url = url(base_url, "/users/{}/public-key/add".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"public_key": SSH_KEY_ED25519}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    user = User.get(session, name=user.username)
    keys = get_public_keys_of_user(session, user.id)
    assert len(keys) == 1
    assert keys[0].public_key == SSH_KEY_ED25519
    assert keys[0].fingerprint == "fa:d9:ca:40:bd:f7:64:37:a7:99:3a:8e:50:8a:c5:94"
    assert keys[0].fingerprint_sha256 == "ExrCZ0nqSJv+LqAEh8CWeKUxiAeZA+N0bKC18dK7Adg"
    assert keys[0].comment == "comment"

    # delete it
    fe_url = url(base_url, "/users/{}/public-key/{}/delete".format(user.username, keys[0].id))
    resp = yield http_client.fetch(
        fe_url, method="POST", body="", headers={"X-Grouper-User": user.username}
    )
    assert resp.code == 200

    user = User.get(session, name=user.username)
    assert not get_public_keys_of_user(session, user.id)


@pytest.mark.gen_test
def test_public_key_admin(session, users, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]
    assert not get_public_keys_of_user(session, user.id)

    # add it
    fe_url = url(base_url, "/users/{}/public-key/add".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"public_key": SSH_KEY_1}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    user = User.get(session, name=user.username)
    keys = get_public_keys_of_user(session, user.id)
    assert len(keys) == 1
    assert keys[0].public_key == SSH_KEY_1

    # have an admin delete it
    fe_url = url(base_url, "/users/{}/public-key/{}/delete".format(user.username, keys[0].id))
    resp = yield http_client.fetch(
        fe_url, method="POST", body="", headers={"X-Grouper-User": "tyleromeara@a.co"}
    )
    assert resp.code == 200

    user = User.get(session, name=user.username)
    assert not get_public_keys_of_user(session, user.id)


@pytest.mark.gen_test
def test_bad_public_key(session, users, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]

    fe_url = url(base_url, "/users/{}/public-key/add".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"public_key": SSH_KEY_BAD}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200
    assert b"Public key appears to be invalid" in resp.body
    assert not get_public_keys_of_user(session, user.id)


@pytest.mark.gen_test
def test_rejected_public_key(session, users, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]

    with patch("grouper.public_key.add_public_key") as add_public_key:
        add_public_key.side_effect = BadPublicKey("Your key is bad and you should feel bad")

        fe_url = url(base_url, "/users/{}/public-key/add".format(user.username))
        resp = yield http_client.fetch(
            fe_url,
            method="POST",
            body=urlencode({"public_key": SSH_KEY_1}),
            headers={"X-Grouper-User": user.username},
        )
    assert resp.code == 200
    assert b"Your key is bad and you should feel bad" in resp.body
    assert not get_public_keys_of_user(session, user.id)


@pytest.mark.gen_test
def test_sa_pubkeys(session, users, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]

    # Add account
    create_role_user(session, user, "bob@svc.localhost", "Hi", "canjoin")

    u = User.get(session, name="bob@svc.localhost")
    g = Group.get(session, name="bob@svc.localhost")

    assert u is not None
    assert g is not None
    assert is_role_user(session, user=u)
    assert is_role_user(session, group=g)
    assert get_role_user(session, user=u).group.id == g.id
    assert get_role_user(session, group=g).user.id == u.id
    assert not is_role_user(session, user=user)
    assert not is_role_user(session, group=Group.get(session, name="team-sre"))

    assert not get_public_keys_of_user(session, user.id)

    with pytest.raises(HTTPError):
        # add it
        fe_url = url(base_url, "/users/{}/public-key/add".format("bob@svc.localhost"))
        resp = yield http_client.fetch(
            fe_url,
            method="POST",
            body=urlencode({"public_key": SSH_KEY_1}),
            headers={"X-Grouper-User": "gary@a.co"},
        )

    # add it
    fe_url = url(base_url, "/users/{}/public-key/add".format("bob@svc.localhost"))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"public_key": SSH_KEY_1}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    # add bad key -- shouldn't add
    fe_url = url(base_url, "/users/{}/public-key/add".format("bob@svc.localhost"))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"public_key": SSH_KEY_BAD}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    sa = User.get(session, name="bob@svc.localhost")
    keys = get_public_keys_of_user(session, sa.id)
    assert len(keys) == 1
    assert keys[0].public_key == SSH_KEY_1

    with pytest.raises(HTTPError):
        # delete it
        fe_url = url(
            base_url, "/users/{}/public-key/{}/delete".format("bob@svc.localhost", keys[0].id)
        )
        resp = yield http_client.fetch(
            fe_url, method="POST", body="", headers={"X-Grouper-User": "gary@a.co"}
        )

    # delete it
    fe_url = url(
        base_url, "/users/{}/public-key/{}/delete".format("bob@svc.localhost", keys[0].id)
    )
    resp = yield http_client.fetch(
        fe_url, method="POST", body="", headers={"X-Grouper-User": user.username}
    )
    assert resp.code == 200

    sa = User.get(session, name="bob@svc.localhost")
    assert not get_public_keys_of_user(session, sa.id)


@pytest.mark.gen_test
def test_usertokens(session, users, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]
    assert len(user.tokens) == 0

    # Add token
    fe_url = url(base_url, "/users/{}/tokens/add".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"name": "myFoobarToken"}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    # Verify add
    fe_url = url(base_url, "/users/{}".format(user.username))
    resp = yield http_client.fetch(fe_url, method="GET", headers={"X-Grouper-User": user.username})
    assert resp.code == 200
    assert b"Added token: myFoobarToken" in resp.body

    # Disable token
    fe_url = url(base_url, "/users/{}/tokens/1/disable".format(user.username))
    resp = yield http_client.fetch(
        fe_url, method="POST", body="", headers={"X-Grouper-User": user.username}
    )
    assert resp.code == 200

    # Verify disable
    fe_url = url(base_url, "/users/{}".format(user.username))
    resp = yield http_client.fetch(fe_url, method="GET", headers={"X-Grouper-User": user.username})
    assert resp.code == 200
    assert b"Disabled token: myFoobarToken" in resp.body

    # Add invalid token
    fe_url = url(base_url, "/users/{}/tokens/add".format(user.username))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"name": "my_Foobar_Token"}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    # Verify noadd
    fe_url = url(base_url, "/users/{}".format(user.username))
    resp = yield http_client.fetch(fe_url, method="GET", headers={"X-Grouper-User": user.username})
    assert resp.code == 200
    assert b"Added token: my_Foobar_Token" not in resp.body


@pytest.mark.gen_test
def test_sa_tokens(session, users, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]

    # Add account
    create_role_user(session, user, "bob@svc.localhost", "Hi", "canjoin")

    u = User.get(session, name="bob@svc.localhost")
    g = Group.get(session, name="bob@svc.localhost")

    assert u is not None
    assert g is not None
    assert is_role_user(session, user=u)
    assert is_role_user(session, group=g)
    assert get_role_user(session, user=u).group.id == g.id
    assert get_role_user(session, group=g).user.id == u.id
    assert not is_role_user(session, user=user)
    assert not is_role_user(session, group=Group.get(session, name="team-sre"))

    with pytest.raises(HTTPError):
        # Add token
        fe_url = url(base_url, "/users/{}/tokens/add".format("bob@svc.localhost"))
        resp = yield http_client.fetch(
            fe_url,
            method="POST",
            body=urlencode({"name": "myDHDToken"}),
            headers={"X-Grouper-User": "gary@a.co"},
        )

    # Add token
    fe_url = url(base_url, "/users/{}/tokens/add".format("bob@svc.localhost"))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"name": "myDHDToken"}),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    # Verify add
    fe_url = url(base_url, "/users/{}".format("bob@svc.localhost"))
    resp = yield http_client.fetch(fe_url, method="GET", headers={"X-Grouper-User": user.username})
    assert resp.code == 200
    assert b"Added token: myDHDToken" in resp.body

    with pytest.raises(HTTPError):
        # Disable token
        fe_url = url(base_url, "/users/{}/tokens/1/disable".format("bob@svc.localhost"))
        resp = yield http_client.fetch(
            fe_url, method="POST", body="", headers={"X-Grouper-User": "gary@a.co"}
        )

    # Disable token
    fe_url = url(base_url, "/users/{}/tokens/1/disable".format("bob@svc.localhost"))
    resp = yield http_client.fetch(
        fe_url, method="POST", body="", headers={"X-Grouper-User": user.username}
    )
    assert resp.code == 200

    # Verify disable
    fe_url = url(base_url, "/users/{}".format("bob@svc.localhost"))
    resp = yield http_client.fetch(fe_url, method="GET", headers={"X-Grouper-User": user.username})
    assert resp.code == 200
    assert b"Disabled token: myDHDToken" in resp.body


@pytest.mark.gen_test
def test_request_emails_reference(
    session, groups, permissions, users, base_url, http_client  # noqa: F811
):
    tech = groups["tech-ops"]

    tech.canjoin = "canask"
    tech.add(session)
    session.commit()

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    fe_url = url(base_url, "/groups/{}/join".format(tech.groupname))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode(
            {"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name)}
        ),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    zay_emails = _get_unsent_and_mark_as_sent_emails_with_username(session, "zay@a.co")
    assert any(["References: " in email.body for email in zay_emails])


@pytest.mark.gen_test
def test_request_emails(
    graph, groups, permissions, session, standard_graph, users, base_url, http_client  # noqa: F811
):
    tech = groups["tech-ops"]

    tech.canjoin = "canask"
    tech.add(session)
    session.commit()

    # REQUEST 1

    before_reqs = session.query(Request).count()

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    fe_url = url(base_url, "/groups/{}/join".format(tech.groupname))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode(
            {"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name)}
        ),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    zaya_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "zay@a.co"))
    fh_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "figurehead@a.co"))

    assert (
        zaya_emails + fh_emails == 2
    ), "Only approvers for the requested group should receive an email"
    assert zaya_emails == 1, "Owners should receive exactly one email per canask request"
    assert fh_emails == 1, "NP-Owners should receive exactly one email per canask request"

    assert (
        session.query(Request).count() == before_reqs + 1
    ), "There should only be one added request"

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request_id = (
        session.query(Request).filter_by(requesting_id=tech.id, requester_id=user.id).scalar().id
    )
    fe_url = url(base_url, "/groups/{}/requests/{}".format(tech.groupname, request_id))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"reason": "Test Response Please Ignore", "status": "actioned"}),
        headers={"X-Grouper-User": "zay@a.co"},
    )
    assert resp.code == 200

    fh_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "figurehead@a.co"))
    testuser_emails = len(
        _get_unsent_and_mark_as_sent_emails_with_username(session, "testuser@a.co")
    )

    assert (
        fh_emails + testuser_emails == 2
    ), "Only the approver that didn't action the request and the reqester should get an email"
    assert fh_emails == 1, "NP-owners that did not action the request should receive an email"
    assert (
        testuser_emails == 1
    ), "The requester should receive an email when the request is handled"

    # REQUEST 2

    before_reqs = session.query(Request).count()

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="oliver@a.co").scalar()
    fe_url = url(base_url, "/groups/{}/join".format(tech.groupname))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode(
            {"reason": "Test Request Please Ignore 2", "member": "User: {}".format(user.name)}
        ),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    zaya_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "zay@a.co"))
    fh_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "figurehead@a.co"))

    assert (
        zaya_emails + fh_emails == 2
    ), "Only approvers for the requested group should receive an email"
    assert zaya_emails == 1, "Owners should receive exactly one email per canask request"
    assert fh_emails == 1, "NP-Owners should receive exactly one email per canask request"

    assert (
        session.query(Request).count() == before_reqs + 1
    ), "There should only be one added request"

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="oliver@a.co").scalar()
    request_id = (
        session.query(Request).filter_by(requesting_id=tech.id, requester_id=user.id).scalar().id
    )
    fe_url = url(base_url, "/groups/{}/requests/{}".format(tech.groupname, request_id))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode({"reason": "Test Response Please Ignore 2", "status": "actioned"}),
        headers={"X-Grouper-User": "figurehead@a.co"},
    )
    assert resp.code == 200

    zaya_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "zay@a.co"))
    oliver_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "oliver@a.co"))

    assert (
        zaya_emails + oliver_emails == 2
    ), "Only the approver that didn't action the request and the reqester should get an email"
    assert zaya_emails == 1, "NP-owners that did not action the request should receive an email"
    assert oliver_emails == 1, "The requester should receive an email when the request is handled"


@pytest.mark.gen_test
def test_request_autoexpiration(
    graph, groups, permissions, session, standard_graph, users, base_url, http_client  # noqa: F811
):
    tech = groups["tech-ops"]
    sre = groups["team-sre"]
    security = groups["security-team"]
    sad = groups["sad-team"]
    infra = groups["team-infra"]

    tech.canjoin = "canask"
    tech.auto_expire = timedelta(days=5)
    tech.add(session)
    session.commit()

    sre.canjoin = "canjoin"
    sre.auto_expire = timedelta(days=500)
    sre.add(session)
    session.commit()

    security.canjoin = "canjoin"
    security.add(session)
    session.commit()

    sad.canjoin = "canjoin"
    sad.add(session)
    session.commit()

    infra.canjoin = "canjoin"
    infra.add(session)
    session.commit()

    # REQUEST 1

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    tech = session.query(Group).filter_by(groupname="tech-ops").scalar()
    fe_url = url(base_url, "/groups/{}/join".format(tech.groupname))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode(
            {"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name)}
        ),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request = (
        session.query(Request).filter_by(requesting_id=tech.id, requester_id=user.id).scalar()
    )
    assert datetime.strptime(request.changes["expiration"], "%m/%d/%Y").date() == (
        datetime.utcnow().date() + tech.auto_expire
    ), "Request expirations should be the current date + group.auto_expire for canask groups"

    # REQUEST 2

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    sre = session.query(Group).filter_by(groupname="team-sre").scalar()
    fe_url = url(base_url, "/groups/{}/join".format(sre.groupname))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode(
            {"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name)}
        ),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request = session.query(Request).filter_by(requesting_id=sre.id, requester_id=user.id).scalar()
    assert datetime.strptime(request.changes["expiration"], "%m/%d/%Y").date() == (
        datetime.utcnow().date() + sre.auto_expire
    ), "Request expirations should be the current date + group.auto_expire for canjoin groups"

    # REQUEST 3

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    security = session.query(Group).filter_by(groupname="security-team").scalar()
    fe_url = url(base_url, "/groups/{}/join".format(security.groupname))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode(
            {"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name)}
        ),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request = (
        session.query(Request).filter_by(requesting_id=security.id, requester_id=user.id).scalar()
    )
    assert "expiration" not in request.changes, (
        "The request should not have an expiration if none is provided and there is no"
        " auto_expiration"
    )

    # REQUEST 4

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    sad = session.query(Group).filter_by(groupname="sad-team").scalar()
    fe_url = url(base_url, "/groups/{}/join".format(sad.groupname))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode(
            {
                "reason": "Test Request Please Ignore",
                "member": "User: {}".format(user.name),
                "expiration": "01/19/2038",
            }
        ),
        headers={"X-Grouper-User": user.username},
    )
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request = session.query(Request).filter_by(requesting_id=sad.id, requester_id=user.id).scalar()
    assert datetime.strptime(request.changes["expiration"], "%m/%d/%Y").date() == date(
        year=2038, month=1, day=19
    ), "User provided expiration times should not be overwritten by the auto_expiration"

    # REQUEST 5

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    infra = session.query(Group).filter_by(groupname="team-infra").scalar()
    fe_url = url(base_url, "/groups/{}/add".format(infra.groupname))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode(
            {"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name)}
        ),
        headers={"X-Grouper-User": "gary@a.co"},
    )
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request = (
        session.query(Request).filter_by(requesting_id=infra.id, requester_id=user.id).scalar()
    )
    assert "expiration" not in request.changes, (
        "The request should not have an expiration if none is provided and the request was"
        " created by adding a member"
    )

    # REQUEST 6

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    sre = session.query(Group).filter_by(groupname="team-sre").scalar()
    fe_url = url(base_url, "/groups/{}/edit/user/{}".format(sre.groupname, user.name))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        body=urlencode(
            {
                "reason": "Test Request Please Ignore",
                "member": "User: {}".format(user.name),
                "role": "member",
                "expiration": "",
            }
        ),
        headers={"X-Grouper-User": "gary@a.co"},
    )
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    group_edge = session.query(GroupEdge).filter_by(group_id=sre.id, member_pk=user.id).scalar()
    assert group_edge.expiration is None, (
        "The request should not have an expiration if none is provided and the user was edited"
        " by an approver"
    )


@pytest.mark.gen_test
def test_add_role_user(session, users, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]

    # Add account
    create_role_user(session, user, "bob@svc.localhost", "Hi", "canjoin")

    u = User.get(session, name="bob@svc.localhost")
    g = Group.get(session, name="bob@svc.localhost")

    assert u is not None
    assert g is not None
    assert is_role_user(session, user=u)
    assert is_role_user(session, group=g)
    assert get_role_user(session, user=u).group.id == g.id
    assert get_role_user(session, group=g).user.id == u.id
    assert not is_role_user(session, user=user)
    assert not is_role_user(session, group=Group.get(session, name="team-sre"))


@pytest.mark.gen_test
def test_disable_role_user(session, users, http_client, base_url):  # noqa: F811
    user = users["zorkian@a.co"]

    # Add account
    create_role_user(session, user, "bob@svc.localhost", "Hi", "canjoin")

    u = User.get(session, name="bob@svc.localhost")
    g = Group.get(session, name="bob@svc.localhost")

    assert u is not None
    assert g is not None
    assert is_role_user(session, user=u)
    assert is_role_user(session, group=g)
    assert get_role_user(session, user=u).group.id == g.id
    assert get_role_user(session, group=g).user.id == u.id
    assert not is_role_user(session, user=user)
    assert not is_role_user(session, group=Group.get(session, name="team-sre"))

    disable_role_user(session, user=u)
    u = User.get(session, name="bob@svc.localhost")
    assert not u.enabled, "The SA User should be disabled"
    g = Group.get(session, name="bob@svc.localhost")
    assert not g.enabled, "The SA Group should be disabled"

    enable_role_user(session, actor=user, group=g, preserve_membership=True)
    u = User.get(session, name="bob@svc.localhost")
    assert u.enabled, "The SA User should be enabled"
    g = Group.get(session, name="bob@svc.localhost")
    assert g.enabled, "The SA Group should be enabled"

    with pytest.raises(HTTPError):
        fe_url = url(base_url, "/groups/{}/disable".format("bob@svc.localhost"))
        yield http_client.fetch(
            fe_url, method="POST", body="", headers={"X-Grouper-User": user.username}
        )

    u = User.get(session, name="bob@svc.localhost")
    assert u.enabled, "Attempting to disable SAs through groups/disable should not work"
    g = Group.get(session, name="bob@svc.localhost")
    assert g.enabled, "Attempting to disable SAs through groups/disable should not work"

    fe_url = url(base_url, "/users/{}/disable".format("bob@svc.localhost"))
    yield http_client.fetch(
        fe_url, method="POST", body="", headers={"X-Grouper-User": user.username}
    )

    u = User.get(session, name="bob@svc.localhost")
    assert not u.enabled, "The SA User should be disabled"
    g = Group.get(session, name="bob@svc.localhost")
    assert not g.enabled, "The SA Group should be disabled"

    with pytest.raises(HTTPError):
        fe_url = url(base_url, "/groups/{}/enable".format("bob@svc.localhost"))
        yield http_client.fetch(
            fe_url, method="POST", body="", headers={"X-Grouper-User": user.username}
        )

    u = User.get(session, name="bob@svc.localhost")
    assert not u.enabled, "Attempting to enable SAs through groups/enable should not work"
    g = Group.get(session, name="bob@svc.localhost")
    assert not g.enabled, "Attempting to enable SAs through groups/enable should not work"


@pytest.mark.gen_test
def test_group_request(session, users, groups, http_client, base_url):  # noqa: F811
    user = users["cbguder@a.co"]
    group = groups["sad-team"]

    # Request to join

    fe_url = url(base_url, "/groups/{}/join".format(group.groupname))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        headers={"X-Grouper-User": user.username},
        body=urlencode({"reason": "Test Request", "member": "User: cbguder@a.co"}),
    )
    assert resp.code == 200

    request = Request.get(session, requester_id=user.id, requesting_id=group.id)
    assert request.status == "pending"

    # Approve request

    fe_url = url(base_url, "/groups/{}/requests/{}".format(group.groupname, request.id))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        headers={"X-Grouper-User": "zorkian@a.co"},
        body=urlencode({"reason": "Test Request", "status": "actioned"}),
    )
    assert resp.code == 200

    request = Request.get(session, requester_id=user.id, requesting_id=group.id)
    assert request.status == "actioned"


@pytest.mark.gen_test
def test_group_request_cancelled(session, users, groups, http_client, base_url):  # noqa: F811
    user = users["cbguder@a.co"]
    group = groups["sad-team"]

    # Request to join

    fe_url = url(base_url, "/groups/{}/join".format(group.groupname))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        headers={"X-Grouper-User": user.username},
        body=urlencode({"reason": "Test Request", "member": "User: cbguder@a.co"}),
    )
    assert resp.code == 200

    request = Request.get(session, requester_id=user.id, requesting_id=group.id)
    assert request.status == "pending"

    # Cancel request

    fe_url = url(base_url, "/groups/{}/requests/{}".format(group.groupname, request.id))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        headers={"X-Grouper-User": user.username},
        body=urlencode({"reason": "Test Request", "status": "cancelled"}),
    )
    assert resp.code == 200

    request = Request.get(session, requester_id=user.id, requesting_id=group.id)
    assert request.status == "cancelled"

    # Approve request (Fails)

    fe_url = url(base_url, "/groups/{}/requests/{}".format(group.groupname, request.id))
    resp = yield http_client.fetch(
        fe_url,
        method="POST",
        headers={"X-Grouper-User": "zorkian@a.co"},
        body=urlencode({"reason": "Test Request", "status": "actioned"}),
    )
    assert resp.code == 200
    assert b"Request has already been processed" in resp.body

    request = Request.get(session, requester_id=user.id, requesting_id=group.id)
    assert request.status == "cancelled"


@pytest.mark.gen_test
def test_request_logging(session, users, http_client, base_url):  # noqa: F811
    """Test that the fe request handlers properly log stats"""
    mock_plugin = Mock()
    get_plugin_proxy().add_plugin(mock_plugin)

    user = users["zorkian@a.co"]
    fe_url = url(base_url, "/users")
    start_time = time.time()
    resp = yield http_client.fetch(fe_url, method="GET", headers={"X-Grouper-User": user.username})
    duration_ms = (time.time() - start_time) * 1000
    assert resp.code == 200
    assert mock_plugin.log_request.call_count == 1
    assert mock_plugin.log_request.call_args_list[0][0][0] == "UsersView"
    assert mock_plugin.log_request.call_args_list[0][0][1] == 200
    # the reported value should be within 1s of our own observation
    assert abs(mock_plugin.log_request.call_args_list[0][0][2] - duration_ms) <= 1000
    assert mock_plugin.log_request.call_args_list[0][0][3].path == "/users"

    mock_plugin.log_request.reset_mock()
    start_time = time.time()
    with pytest.raises(HTTPError):
        fe_url = url(base_url, "/groups/{}".format("does-not-exist"))
        resp = yield http_client.fetch(
            fe_url, method="GET", headers={"X-Grouper-User": user.username}
        )
    duration_ms = (time.time() - start_time) * 1000
    assert mock_plugin.log_request.call_count == 1
    assert mock_plugin.log_request.call_args_list[0][0][0] == "GroupView"
    assert mock_plugin.log_request.call_args_list[0][0][1] == 404
    # the reported value should be within 1s of our own observation
    assert abs(mock_plugin.log_request.call_args_list[0][0][2] - duration_ms) <= 1000
    assert mock_plugin.log_request.call_args_list[0][0][3].path == "/groups/does-not-exist"
