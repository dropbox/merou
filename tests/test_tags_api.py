import json

import pytest

from fixtures import api_app as app  # noqa
from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from grouper.constants import TAG_EDIT
from grouper.model_soup import Group
from grouper.models.permission import Permission
from grouper.models.public_key import PublicKey
from grouper.models.public_key_tag import PublicKeyTag
from grouper.models.user import User
from grouper.permissions import grant_permission_to_tag
from grouper.public_key import add_public_key, add_tag_to_public_key, get_public_key_permissions
from grouper.user_permissions import user_permissions
from url_util import url
from util import grant_permission


key1 = ('ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDCUQeasspT/etEJR2WUoR+h2sMOQYbJgr0Q'
        'E+J8p97gEhmz107KWZ+3mbOwyIFzfWBcJZCEg9wy5Paj+YxbGONqbpXAhPdVQ2TLgxr41bNXvbcR'
        'AxZC+Q12UZywR4Klb2kungKz4qkcmSZzouaKK12UxzGB3xQ0N+3osKFj3xA1+B6HqrVreU19XdVo'
        'AJh0xLZwhw17/NDM+dAcEdMZ9V89KyjwjraXtOVfFhQF0EDF0ame8d6UkayGrAiXC2He0P2Cja+J'
        '371P27AlNLHFJij8WGxvcGGSeAxMLoVSDOOllLCYH5UieV8mNpX1kNe2LeA58ciZb0AXHaipSmCH'
        'gh/ some-comment')


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
    #assert len(pub_key['permissions']) == 1, "The public key should only have 1 permission"
    #assert pub_key['permissions'][0] == [TAG_EDIT, "prod"], "The public key should only have permissions that are the intersection of the user's permissions and the tag's permissions"
