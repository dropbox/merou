import json
from urllib import urlencode

import pytest
from tornado.httpclient import HTTPError

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from grouper import public_key
from grouper.model_soup import  Request, AsyncNotification, Group, GroupEdge
from grouper.models.user import User
from grouper.public_key import get_public_keys_of_user
from grouper.service_account import get_service_account, is_service_account
from url_util import url
from datetime import timedelta, datetime, date


def _get_unsent_and_mark_as_sent_emails_with_username(session, username):
    """Helper to count unsent emails and then mark them as sent."""
    emails = session.query(AsyncNotification).filter_by(sent=False, email=username).all()

    for email in emails:
        email.sent = True

    session.commit()
    return emails

@pytest.mark.gen_test
def test_auth(users, http_client, base_url):
    # no 'auth' present
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(base_url)

    # invalid user
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(base_url, headers={'X-Grouper-User': 'nobody'})

    # valid user
    resp = yield http_client.fetch(base_url, headers={'X-Grouper-User': 'zorkian@a.co'})
    assert resp.code == 200


@pytest.mark.gen_test
def test_public_key(session, users, http_client, base_url):
    user = users['zorkian@a.co']
    assert not get_public_keys_of_user(session, user.id)

    good_key = ('ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDCUQeasspT/etEJR2WUoR+h2sMOQYbJgr0Q'
            'E+J8p97gEhmz107KWZ+3mbOwyIFzfWBcJZCEg9wy5Paj+YxbGONqbpXAhPdVQ2TLgxr41bNXvbcR'
            'AxZC+Q12UZywR4Klb2kungKz4qkcmSZzouaKK12UxzGB3xQ0N+3osKFj3xA1+B6HqrVreU19XdVo'
            'AJh0xLZwhw17/NDM+dAcEdMZ9V89KyjwjraXtOVfFhQF0EDF0ame8d6UkayGrAiXC2He0P2Cja+J'
            '371P27AlNLHFJij8WGxvcGGSeAxMLoVSDOOllLCYH5UieV8mNpX1kNe2LeA58ciZb0AXHaipSmCH'
            'gh/ some-comment')

    bad_key = 'ssh-rsa AAAblahblahkey some-comment'

    # add it
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': good_key}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    # add bad key -- shouldn't add
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': bad_key}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = User.get(session, name=user.username)
    keys = get_public_keys_of_user(session, user.id)
    assert len(keys) == 1
    assert keys[0].public_key == good_key

    # delete it
    fe_url = url(base_url, '/users/{}/public-key/{}/delete'.format(user.username, keys[0].id))
    resp = yield http_client.fetch(fe_url, method="POST", body='',
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = User.get(session, name=user.username)
    assert not get_public_keys_of_user(session, user.id)

@pytest.mark.gen_test
def test_usertokens(session, users, http_client, base_url):
    user = users['zorkian@a.co']
    assert len(user.tokens) == 0

    # Add token
    fe_url = url(base_url, '/users/{}/tokens/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'name': 'myFoobarToken'}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    # Verify add
    fe_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="GET",
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200
    assert "Added token: myFoobarToken" in resp.body

    # Disable token
    fe_url = url(base_url, '/users/{}/tokens/1/disable'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body="",
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    # Verify disable
    fe_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="GET",
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200
    assert "Disabled token: myFoobarToken" in resp.body

    # Add invalid token
    fe_url = url(base_url, '/users/{}/tokens/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'name': 'my_Foobar_Token'}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    # Verify noadd
    fe_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="GET",
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200
    assert "Added token: my_Foobar_Token" not in resp.body



@pytest.mark.gen_test
def test_request_emails(graph, groups, permissions, session, standard_graph, users, base_url,
                        http_client):
    tech = groups["tech-ops"]

    tech.canjoin = "canask"
    tech.add(session)
    session.commit()

    # REQUEST 1

    before_reqs = session.query(Request).count()

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    fe_url = url(base_url, '/groups/{}/join'.format(tech.groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name)}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    zaya_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "zay@a.co"))
    fh_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "figurehead@a.co"))

    assert zaya_emails + fh_emails == 2, "Only approvers for the requested group should receive an email"
    assert zaya_emails == 1, "Owners should receive exactly one email per canask request"
    assert fh_emails == 1, "NP-Owners should receive exactly one email per canask request"

    assert session.query(Request).count() == before_reqs + 1, "There should only be one added request"

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request_id = session.query(Request).filter_by(requesting_id=tech.id, requester_id=user.id).scalar().id
    fe_url = url(base_url, '/groups/{}/requests/{}'.format(tech.groupname, request_id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"reason": "Test Response Please Ignore", "status": "actioned"}),
            headers={'X-Grouper-User': "zay@a.co"})
    assert resp.code == 200

    fh_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "figurehead@a.co"))
    testuser_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "testuser@a.co"))

    assert fh_emails + testuser_emails == 2, "Only the approver that didn't action the request and the reqester should get an email"
    assert fh_emails == 1, "NP-owners that did not action the request should receive an email"
    assert testuser_emails == 1, "The requester should receive an email when the request is handled"

    # REQUEST 2

    before_reqs = session.query(Request).count()

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="oliver@a.co").scalar()
    fe_url = url(base_url, '/groups/{}/join'.format(tech.groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"reason": "Test Request Please Ignore 2", "member": "User: {}".format(user.name)}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    zaya_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "zay@a.co"))
    fh_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "figurehead@a.co"))

    assert zaya_emails + fh_emails == 2, "Only approvers for the requested group should receive an email"
    assert zaya_emails == 1, "Owners should receive exactly one email per canask request"
    assert fh_emails == 1, "NP-Owners should receive exactly one email per canask request"

    assert session.query(Request).count() == before_reqs + 1, "There should only be one added request"

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="oliver@a.co").scalar()
    request_id = session.query(Request).filter_by(requesting_id=tech.id, requester_id=user.id).scalar().id
    fe_url = url(base_url, '/groups/{}/requests/{}'.format(tech.groupname, request_id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"reason": "Test Response Please Ignore 2", "status": "actioned"}),
            headers={'X-Grouper-User': "figurehead@a.co"})
    assert resp.code == 200

    zaya_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "zay@a.co"))
    oliver_emails = len(_get_unsent_and_mark_as_sent_emails_with_username(session, "oliver@a.co"))

    assert zaya_emails + oliver_emails == 2, "Only the approver that didn't action the request and the reqester should get an email"
    assert zaya_emails == 1, "NP-owners that did not action the request should receive an email"
    assert oliver_emails == 1, "The requester should receive an email when the request is handled"

@pytest.mark.gen_test
def test_request_autoexpiration(graph, groups, permissions, session, standard_graph, users,
                                base_url, http_client):
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
    fe_url = url(base_url, '/groups/{}/join'.format(tech.groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name)}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request = session.query(Request).filter_by(requesting_id=tech.id, requester_id=user.id).scalar()
    assert datetime.strptime(json.loads(request.changes)['expiration'], "%m/%d/%Y").date() == (datetime.utcnow().date() + tech.auto_expire), "Request expirations should be the current date + group.auto_expire for canask groups"

    # REQUEST 2

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    sre = session.query(Group).filter_by(groupname="team-sre").scalar()
    fe_url = url(base_url, '/groups/{}/join'.format(sre.groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name)}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request = session.query(Request).filter_by(requesting_id=sre.id, requester_id=user.id).scalar()
    assert datetime.strptime(json.loads(request.changes)['expiration'], "%m/%d/%Y").date() == (datetime.utcnow().date() + sre.auto_expire), "Request expirations should be the current date + group.auto_expire for canjoin groups"

    # REQUEST 3

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    security = session.query(Group).filter_by(groupname="security-team").scalar()
    fe_url = url(base_url, '/groups/{}/join'.format(security.groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name)}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request = session.query(Request).filter_by(requesting_id=security.id, requester_id=user.id).scalar()
    assert "expiration" not in json.loads(request.changes), "The request should not have an expiration if none is provided and there is no auto_expiration"

    # REQUEST 4

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    sad = session.query(Group).filter_by(groupname="sad-team").scalar()
    fe_url = url(base_url, '/groups/{}/join'.format(sad.groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name), "expiration": "01/19/2038"}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request = session.query(Request).filter_by(requesting_id=sad.id, requester_id=user.id).scalar()
    assert datetime.strptime(json.loads(request.changes)['expiration'], "%m/%d/%Y").date() == date(year=2038, month=1, day=19), "User provided expiration times should not be overwritten by the auto_expiration"

    # REQUEST 5

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    infra = session.query(Group).filter_by(groupname="team-infra").scalar()
    fe_url = url(base_url, '/groups/{}/add'.format(infra.groupname))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name)}),
            headers={'X-Grouper-User': "gary@a.co"})
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    request = session.query(Request).filter_by(requesting_id=infra.id, requester_id=user.id).scalar()
    assert "expiration" not in json.loads(request.changes), "The request should not have an expiration if none is provided and the request was created by adding a member"

    # REQUEST 6

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    sre = session.query(Group).filter_by(groupname="team-sre").scalar()
    fe_url = url(base_url, '/groups/{}/edit/user/{}'.format(sre.groupname, user.name))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"reason": "Test Request Please Ignore", "member": "User: {}".format(user.name), "role": "member", "expiration": ""}),
            headers={'X-Grouper-User': "gary@a.co"})
    assert resp.code == 200

    # Explicitly requery because pulling from the users dict causes DetachedSessionErrors
    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    group_edge = session.query(GroupEdge).filter_by(group_id=sre.id, member_pk=user.id).scalar()
    assert group_edge.expiration is None, "The request should not have an expiration if none is provided and the user was edited by an approver"


@pytest.mark.gen_test
def test_add_service_account(session, users, http_client, base_url):
    user = users['zorkian@a.co']

    # Add account
    fe_url = url(base_url, '/users/service_create')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'name': 'bob@hello.com', "description": "Hi", "canjoin": "canjoin"}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    assert User.get(session, name="bob@hello.com") is None
    assert Group.get(session, name="bob@hello.com") is None

    # Add account
    fe_url = url(base_url, '/users/service_create')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'name': 'bob@svc.localhost', "description": "Hi", "canjoin": "canjoin"}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    u = User.get(session, name="bob@svc.localhost")
    g = Group.get(session, name="bob@svc.localhost")

    assert u is not None
    assert g is not None
    assert is_service_account(session, user=u)
    assert is_service_account(session, group=g)
    assert get_service_account(session, user=u)["group"].id == g.id
    assert get_service_account(session, group=g)["user"].id == u.id
    assert not is_service_account(session, user=user)
    assert not is_service_account(session, group=Group.get(session, name="team-sre"))
