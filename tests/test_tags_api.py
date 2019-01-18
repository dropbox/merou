import json

import pytest

from constants import SSH_KEY_1
from fixtures import api_app as app  # noqa
from fixtures import standard_graph, graph, users, groups, service_accounts, session, permissions  # noqa
from grouper.constants import TAG_EDIT
from grouper.models.group import Group
from grouper.models.public_key import PublicKey
from grouper.models.public_key_tag import PublicKeyTag
from grouper.models.user import User
from grouper.permissions import create_permission, get_permission, grant_permission_to_tag
from grouper.public_key import add_public_key, add_tag_to_public_key, get_public_key_permissions
from grouper.user_permissions import user_permissions
from url_util import url
from util import grant_permission


@pytest.mark.gen_test
def test_tags(session, http_client, base_url, graph):
    perm = create_permission(session, TAG_EDIT)
    session.commit()

    perm2 = create_permission(session, "it.literally.does.not.matter")
    session.commit()

    grant_permission(session.query(Group).filter_by(groupname="all-teams").scalar(), get_permission(session, TAG_EDIT), "*")
    grant_permission(session.query(Group).filter_by(groupname="all-teams").scalar(), get_permission(session, "it.literally.does.not.matter"), "*")

    tag = PublicKeyTag(name="tyler_was_here")
    tag.add(session)
    session.commit()

    tag = PublicKeyTag.get(session, name="tyler_was_here")

    grant_permission_to_tag(session, tag.id, perm.id, "prod")
    with pytest.raises(AssertionError):
        grant_permission_to_tag(session, tag.id, perm.id, "question?")

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    add_public_key(session, user, SSH_KEY_1)

    key = session.query(PublicKey).filter_by(user_id=user.id).scalar()

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
    assert pub_key['fingerprint'] == 'e9:ae:c5:8f:39:9b:3a:9c:6a:b8:33:6b:cb:6f:ba:35'
    assert pub_key['fingerprint_sha256'] == 'MP9uWaujW96EWxbjDtPdPWheoMDu6BZ8FZj0+CBkVWU'
    assert pub_key['tags'][0] == 'tyler_was_here', "The public key should have the tag we gave it"
