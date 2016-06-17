import json

from urllib import urlencode

import pytest

from fixtures import api_app as app  # noqa
from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from grouper.constants import TAG_EDIT, USER_METADATA_SHELL_KEY
from grouper.model_soup import Group
from grouper.models.permission import Permission
from grouper.models.public_key import PublicKey
from grouper.models.public_key_tag import PublicKeyTag
from grouper.models.user import User
from grouper.models.user_token import UserToken
from grouper.permissions import grant_permission_to_tag
from grouper.public_key import add_public_key, add_tag_to_public_key, get_public_key_permissions
from grouper.user_permissions import user_permissions
from grouper.user_metadata import get_user_metadata_by_key, set_user_metadata
from grouper.user_token import add_new_user_token, disable_user_token
from url_util import url
from util import grant_permission


key1 = ('ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDCUQeasspT/etEJR2WUoR+h2sMOQYbJgr0Q'
            'E+J8p97gEhmz107KWZ+3mbOwyIFzfWBcJZCEg9wy5Paj+YxbGONqbpXAhPdVQ2TLgxr41bNXvbcR'
            'AxZC+Q12UZywR4Klb2kungKz4qkcmSZzouaKK12UxzGB3xQ0N+3osKFj3xA1+B6HqrVreU19XdVo'
            'AJh0xLZwhw17/NDM+dAcEdMZ9V89KyjwjraXtOVfFhQF0EDF0ame8d6UkayGrAiXC2He0P2Cja+J'
            '371P27AlNLHFJij8WGxvcGGSeAxMLoVSDOOllLCYH5UieV8mNpX1kNe2LeA58ciZb0AXHaipSmCH'
            'gh/ some-comment')


@pytest.mark.gen_test
def test_users(users, http_client, base_url):
    # without role users
    api_url = url(base_url, '/users')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    users_wo_role = sorted((u for u in users if u != u"role@a.co"))

    print 'user_wo_role={}'.format(users_wo_role)
    print 'res={}'.format(sorted(body["data"]["users"]))
    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["users"]) == users_wo_role

    # with role users
    api_url = url(base_url, '/users', {'include_role_users': 'yes'})
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)
    users_w_role = sorted(users)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["users"]) == users_w_role

    # TODO: test cutoff

@pytest.mark.gen_test
def test_usertokens(users, session, http_client, base_url):
    user = users["zorkian@a.co"]
    tok, secret = add_new_user_token(session, UserToken(user=user, name="Foo"))
    session.commit()

    api_url = url(base_url, '/token/validate')

    # Completely bogus input
    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': 'invalid'}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 1

    valid_token = str(tok) + ":" + secret

    # Valid token
    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': valid_token}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert body["data"]["identity"] == str(tok)
    assert body["data"]["owner"] == user.username
    assert body["data"]["act_as_owner"]
    assert body["data"]["valid"]

    # Token with the last character changed to something invalid
    bad_char = "1" if secret[-1].isalpha() else "a"
    token_with_bad_secret = str(tok) + ":" + secret[:-1] + bad_char

    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': token_with_bad_secret}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 4

    # Token with the token name frobbed to be something invalid
    token_with_bad_name = str(tok) + "z:" + secret

    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': token_with_bad_name}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 2

    # Token with the user frobbed to be something invalid
    token_with_bad_user = "z" + str(tok) + ":" + secret

    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': token_with_bad_user}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 2

    # Token with the user changed to another valid, but wrong user
    token_with_wrong_user = "oliver@a.co/" + tok.name + ":" + secret

    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': token_with_wrong_user}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 2

    # Disabled, but otherwise valid token
    disable_user_token(session, tok)
    session.commit()

    resp = yield http_client.fetch(api_url, method="POST", body=urlencode({'token': valid_token}))
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "error"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["code"] == 3



@pytest.mark.gen_test
def test_permissions(permissions, http_client, base_url):
    api_url = url(base_url, '/permissions')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["permissions"]) == sorted(permissions)


@pytest.mark.gen_test
def test_groups(groups, http_client, base_url):
    api_url = url(base_url, '/groups')
    resp = yield http_client.fetch(api_url)
    body = json.loads(resp.body)

    assert resp.code == 200
    assert body["status"] == "ok"
    assert sorted(body["data"]["groups"]) == sorted(groups)

    # TODO: test cutoff

@pytest.mark.gen_test
def test_shell(session, users, http_client, base_url, graph):
    user = users['zorkian@a.co']
    assert not get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY)

    set_user_metadata(session, user.id, USER_METADATA_SHELL_KEY, "/bin/bash")
    graph.update_from_db(session)

    fe_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(fe_url)
    assert resp.code == 200
    body = json.loads(resp.body)
    assert body["data"]["user"]["metadata"] != [], "There should be metadata"
    assert len(body["data"]["user"]["metadata"]) == 1, "There should only be 1 metadata!"
    assert body["data"]["user"]["metadata"][0]["data_key"] == "shell", "There should only be 1 metadata!"
    assert body["data"]["user"]["metadata"][0]["data_value"] == "/bin/bash", "The shell should be set to the correct value"

    set_user_metadata(session, user.id, USER_METADATA_SHELL_KEY, "/bin/zsh")
    graph.update_from_db(session)

    fe_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(fe_url)
    assert resp.code == 200
    body = json.loads(resp.body)
    assert body["data"]["user"]["metadata"] != [], "There should be metadata"
    assert body["data"]["user"]["metadata"][0]["data_key"] == "shell", "There should only be 1 metadata!"
    assert body["data"]["user"]["metadata"][0]["data_value"] == "/bin/zsh", "The shell should be set to the correct value"
    assert len(body["data"]["user"]["metadata"]) == 1, "There should only be 1 metadata!"


@pytest.mark.gen_test
def test_tags(session, users, http_client, base_url, graph):
    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    perm = Permission(name=TAG_EDIT, description="Why is this not nullable?")
    perm.add(session)
    session.commit()

    perm2 = Permission(name="it.literally.does.not.matter", description="Why is this not nullable?")
    perm2.add(session)
    session.commit()

    grant_permission(session.query(Group).filter_by(groupname="all-teams").scalar(), session.query(Permission).filter_by(name=TAG_EDIT).scalar(), "*")
    grant_permission(session.query(Group).filter_by(groupname="all-teams").scalar(), session.query(Permission).filter_by(name="it.literally.does.not.matter").scalar(), "*")

    tag = PublicKeyTag(name="tyler_was_here")
    tag.add(session)
    session.commit()

    tag = PublicKeyTag.get(session, name="tyler_was_here")

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    grant_permission_to_tag(session, tag.id, perm.id, "prod")

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    add_public_key(session, user, key1)

    key = session.query(PublicKey).filter_by(user_id=user.id).scalar()
    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    add_tag_to_public_key(session, key, tag)

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    key = session.query(PublicKey).filter_by(user_id=user.id).scalar()
    assert len(get_public_key_permissions(session, key)) == 1, "The SSH Key should have only 1 permission"
    assert get_public_key_permissions(session, key)[0].name == TAG_EDIT, "The SSH key's permission should be TAG_EDIT"
    assert get_public_key_permissions(session, key)[0].argument == "prod", "The SSH key's permission argument should be restricted to the tag's argument"
    assert len(user_permissions(session, user)) > 1, "The user should have more than 1 permission"

    graph.update_from_db(session)

    fe_url = url(base_url, '/users/{}'.format(user.username))
    resp = yield http_client.fetch(fe_url)
    assert resp.code == 200
    body = json.loads(resp.body)
    pub_key = body['data']['user']['public_keys'][0]
    assert len(pub_key['tags']) == 1, "The public key should only have 1 tag"
    assert pub_key['tags'][0] == 'tyler_was_here', "The public key should have the tag we gave it"
    assert len(pub_key['permissions']) == 1, "The public key should only have 1 permission"
    assert pub_key['permissions'][0] == [TAG_EDIT, "prod"], "The public key should only have permissions that are the intersection of the user's permissions and the tag's permissions"
