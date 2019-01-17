from collections import namedtuple
from urllib import urlencode

import pytest
from tornado.httpclient import HTTPError

from constants import SSH_KEY_1, SSH_KEY_2
from fixtures import fe_app as app
from fixtures import standard_graph, users, graph, groups, service_accounts, session, permissions  # noqa
from grouper.constants import TAG_EDIT
from grouper.models.group import Group
from grouper.models.permission import Permission
from grouper.models.public_key import PublicKey
from grouper.models.public_key_tag import PublicKeyTag
from grouper.models.user import User
from grouper.permissions import get_permission, permission_intersection
from grouper.public_key import get_public_key_permissions, get_public_key_tag_permissions, get_public_key_tags
from grouper.user_permissions import user_permissions
from url_util import url
from util import grant_permission


@pytest.mark.gen_test
def test_create_tag(users, http_client, base_url, session):

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    tag = PublicKeyTag.get(session, name="tyler_was_here")
    assert tag is not None, "The tag should be created"
    assert tag.name == "tyler_was_here", "The tag's name should be tyler_was_here"


@pytest.mark.gen_test
def test_add_tag(users, http_client, base_url, session):

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    # add SSH key
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': SSH_KEY_1}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    key = session.query(PublicKey).filter_by(user_id=user.id).scalar()

    # add SSH key
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': SSH_KEY_2}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    key2 = session.query(PublicKey).filter_by(public_key=SSH_KEY_2).scalar()

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag = PublicKeyTag.get(session, name="tyler_was_here")

    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert get_public_key_tags(session, key) == [], "No public keys should have a tag unless it's been added to the key"

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "dont_tag_me_bro", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag = PublicKeyTag.get(session, name="dont_tag_me_bro")

    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert get_public_key_tags(session, key) == [], "No public keys should have a tag unless it's been added to the key"

    fe_url = url(base_url, '/users/{}/public-key/{}/tag'.format(user.username, key.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here"}),
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200
    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert len(get_public_key_tags(session, key)) == 1, "The key should have exactly 1 tag"
    assert get_public_key_tags(session, key)[0].name == "tyler_was_here"

    key2 = session.query(PublicKey).filter_by(public_key=SSH_KEY_2).scalar()
    assert len(get_public_key_tags(session, key2)) == 0, "Keys other than the one with the added tag should not gain tags"

    # Non-admin and not user adding tag should fail
    fe_url = url(base_url, '/users/{}/public-key/{}/tag'.format(user.username, key.id))
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(fe_url, method="POST",
                body=urlencode({'tagname': "tyler_was_here"}),
                headers={'X-Grouper-User': "zorkian@a.co"})

    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert len(get_public_key_tags(session, key)) == 1, "The key should have exactly 1 tag"
    assert get_public_key_tags(session, key)[0].name == "tyler_was_here"

    # User admins test
    fe_url = url(base_url, '/users/{}/public-key/{}/tag'.format(user.username, key.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "dont_tag_me_bro"}),
            headers={'X-Grouper-User': "tyleromeara@a.co"})

    assert resp.code == 200
    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert len(get_public_key_tags(session, key)) == 2, "The key should have 2 tags now"
    assert set([x.name for x in get_public_key_tags(session, key)]) == set(["tyler_was_here",
        "dont_tag_me_bro"])


@pytest.mark.gen_test
def test_remove_tag(users, http_client, base_url, session):

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    # add SSH key
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': SSH_KEY_1}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    key = session.query(PublicKey).filter_by(user_id=user.id).scalar()

    # add SSH key
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': SSH_KEY_2}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    key2 = session.query(PublicKey).filter_by(public_key=SSH_KEY_2).scalar()

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag = PublicKeyTag.get(session, name="tyler_was_here")

    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert get_public_key_tags(session, key) == [], "No public keys should have a tag unless it's been added to the key"

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "dont_tag_me_bro", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag2 = PublicKeyTag.get(session, name="dont_tag_me_bro")

    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert get_public_key_tags(session, key) == [], "No public keys should have a tag unless it's been added to the key"

    fe_url = url(base_url, '/users/{}/public-key/{}/tag'.format(user.username, key.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here"}),
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200
    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert len(get_public_key_tags(session, key)) == 1, "The key should have exactly 1 tag"
    assert get_public_key_tags(session, key)[0].name == "tyler_was_here"

    key2 = session.query(PublicKey).filter_by(public_key=SSH_KEY_2).scalar()
    assert len(get_public_key_tags(session, key2)) == 0, "Keys other than the one with the added tag should not gain tags"

    fe_url = url(base_url, '/users/{}/public-key/{}/tag'.format(user.username, key2.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here"}),
            headers={'X-Grouper-User': user.username})

    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    # Fail Remove tag
    tag = PublicKeyTag.get(session, name="dont_tag_me_bro")
    fe_url = url(base_url, '/users/{}/public-key/{}/delete_tag/{}'.format(user.username, key.id, tag.id))
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(fe_url, method="POST",
                body="",
                headers={'X-Grouper-User': "oliver@a.co"})

    # Remove tag that isn't on key: should fail silently
    tag = PublicKeyTag.get(session, name="dont_tag_me_bro")
    fe_url = url(base_url, '/users/{}/public-key/{}/delete_tag/{}'.format(user.username, key.id, tag.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body="",
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200

    # Remove tag
    tag = PublicKeyTag.get(session, name="tyler_was_here")
    fe_url = url(base_url, '/users/{}/public-key/{}/delete_tag/{}'.format(user.username, key.id, tag.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body="",
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200

    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert len(get_public_key_tags(session, key)) == 0, "The key should have exactly 0 tags"

    key2 = session.query(PublicKey).filter_by(public_key=SSH_KEY_2).scalar()
    assert len(get_public_key_tags(session, key2)) == 1, "Removing a tag from one key should not affect other keys"

    # User admin remove tag

    # readd tag
    fe_url = url(base_url, '/users/{}/public-key/{}/tag'.format(user.username, key.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here"}),
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200
    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert len(get_public_key_tags(session, key)) == 1, "The key should have exactly 1 tag"
    assert get_public_key_tags(session, key)[0].name == "tyler_was_here"

    # Nonuser admin fail Remove tag
    tag = PublicKeyTag.get(session, name="tyler_was_here")
    fe_url = url(base_url, '/users/{}/public-key/{}/delete_tag/{}'.format(user.username, key.id, tag.id))
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(fe_url, method="POST",
                body="",
                headers={'X-Grouper-User': "oliver@a.co"})

    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert len(get_public_key_tags(session, key)) == 1, "The key should have exactly 1 tags"

    # Remove tag
    tag = PublicKeyTag.get(session, name="tyler_was_here")
    fe_url = url(base_url, '/users/{}/public-key/{}/delete_tag/{}'.format(user.username, key.id, tag.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body="",
            headers={'X-Grouper-User': "tyleromeara@a.co"})

    assert resp.code == 200

    key = session.query(PublicKey).filter_by(public_key=SSH_KEY_1).scalar()
    assert len(get_public_key_tags(session, key)) == 0, "The key should have exactly 0 tags"


@pytest.mark.gen_test
def test_grant_permission_to_tag(users, http_client, base_url, session):

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    perm = Permission(name=TAG_EDIT, description="Why is this not nullable?")
    perm.add(session)
    session.commit()

    grant_permission(session.query(Group).filter_by(groupname="all-teams").scalar(),
                     get_permission(session, TAG_EDIT), "*")

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag = PublicKeyTag.get(session, name="tyler_was_here")

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    fe_url = url(base_url, '/permissions/grant_tag/{}'.format(tag.name))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'permission': TAG_EDIT, "argument": "*"}),
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200
    tag = PublicKeyTag.get(session, name="tyler_was_here")
    perm = get_permission(session, TAG_EDIT)
    assert len(get_public_key_tag_permissions(session, tag)) == 1, "The tag should have exactly 1 permission"
    assert get_public_key_tag_permissions(session, tag)[0].name == perm.name, "The tag's permission should be the one we added"
    assert get_public_key_tag_permissions(session, tag)[0].argument == "*", "The tag's permission should be the one we added"

    # Make sure trying to add a permission to a tag doesn't fail horribly if it's already there
    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    fe_url = url(base_url, '/permissions/grant_tag/{}'.format(tag.name))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'permission': TAG_EDIT, "argument": "*"}),
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200


@pytest.mark.gen_test
def test_edit_tag(users, http_client, base_url, session):

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    perm = Permission(name=TAG_EDIT, description="Why is this not nullable?")
    perm.add(session)
    session.commit()

    grant_permission(session.query(Group).filter_by(groupname="all-teams").scalar(), session.query(Permission).filter_by(name=TAG_EDIT).scalar(), "*")

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag = PublicKeyTag.get(session, name="tyler_was_here")

    assert tag.description == "Test Tag Please Ignore", "The description should match what we created it with"

    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    fe_url = url(base_url, '/tags/{}/edit'.format(tag.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({"description": "Don't tag me bro"}),
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200

    tag = PublicKeyTag.get(session, name="tyler_was_here")

    assert tag.description == "Don't tag me bro", "The description should have been updated"


@pytest.mark.gen_test
def test_permissions(users, http_client, base_url, session):

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    perm = Permission(name=TAG_EDIT, description="Why is this not nullable?")
    perm.add(session)
    session.commit()

    perm = Permission(name="it.literally.does.not.matter", description="Why is this not nullable?")
    perm.add(session)
    session.commit()

    grant_permission(session.query(Group).filter_by(groupname="all-teams").scalar(), session.query(Permission).filter_by(name=TAG_EDIT).scalar(), "*")
    grant_permission(session.query(Group).filter_by(groupname="all-teams").scalar(), session.query(Permission).filter_by(name="it.literally.does.not.matter").scalar(), "*")

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag = PublicKeyTag.get(session, name="tyler_was_here")

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    fe_url = url(base_url, '/permissions/grant_tag/{}'.format(tag.name))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'permission': TAG_EDIT, "argument": "prod"}),
            headers={'X-Grouper-User': user.username})

    user = session.query(User).filter_by(username="testuser@a.co").scalar()
    # add SSH key
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': SSH_KEY_1}),
            headers={'X-Grouper-User': user.username})

    key = session.query(PublicKey).filter_by(user_id=user.id).scalar()
    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    fe_url = url(base_url, '/users/{}/public-key/{}/tag'.format(user.username, key.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here"}),
            headers={'X-Grouper-User': user.username})
    
    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    key = session.query(PublicKey).filter_by(user_id=user.id).scalar()
    assert len(get_public_key_permissions(session, key)) == 1, "The SSH Key should have only 1 permission"
    assert get_public_key_permissions(session, key)[0].name == TAG_EDIT, "The SSH key's permission should be TAG_EDIT"
    assert get_public_key_permissions(session, key)[0].argument == "prod", "The SSH key's permission argument should be restricted to the tag's argument"
    assert len(user_permissions(session, user)) > 1, "The user should have more than 1 permission"

def test_permission_intersection(standard_graph, session, users, groups, permissions):
    p = namedtuple("Permission", ["name", "argument"])
    astar = p("a", "*")
    ar = p("a", "r")
    at = p("a", "t")
    aundef = p("a", "")
    bstar = p("b", "*")
    br = p("b", "r")
    cstar = p("c", "*")
    cr = p("c", "r")

    assert permission_intersection([astar], [astar]) == set([astar]), "The intersection of two identical lists should be the set of the contents of the list"
    assert permission_intersection([ar], [ar]) == set([ar]), "The intersection of two identical lists should be the set of the contents of the list"
    assert permission_intersection([astar], [ar]) == set([ar]), "The intersection of perm, * with perm, blah should be perm, blah"
    assert permission_intersection([ar], [astar]) == set([ar]), "The intersection of perm, blah with perm, * should be perm, blah"

    assert permission_intersection([astar], [bstar]) == set(), "The intersection of two disjoint lists should be the empty set"
    assert permission_intersection([ar], [br]) == set(), "The intersection of two disjoint lists should be the empty set"
    assert permission_intersection([ar], [at]) == set(), "The intersection of two disjoint lists should be the empty set"

    assert permission_intersection([astar], [ar, at]) == set([ar, at]), "Wildcards should result in all applicable permissions being in the result"
    assert permission_intersection([aundef], [ar, at]) == set([aundef]), "Unargumented permissions are always granted by argumented permissions"
    assert permission_intersection([ar, at], [aundef]) == set([aundef]), "Unargumented permissions are always granted by argumented permissions"
    assert permission_intersection([astar, ar, br, cr], [at, bstar, cr]) == set([at, br, cr]), "This should work"

@pytest.mark.gen_test
def test_revoke_permission_from_tag(users, http_client, base_url, session):

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    perm = Permission(name=TAG_EDIT, description="Why is this not nullable?")
    perm.add(session)
    session.commit()

    grant_permission(session.query(Group).filter_by(groupname="all-teams").scalar(), session.query(Permission).filter_by(name=TAG_EDIT).scalar(), "*")

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag = PublicKeyTag.get(session, name="tyler_was_here")

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    fe_url = url(base_url, '/permissions/grant_tag/{}'.format(tag.name))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'permission': TAG_EDIT, "argument": "*"}),
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200
    tag = PublicKeyTag.get(session, name="tyler_was_here")
    perm = get_permission(session, TAG_EDIT)
    assert len(get_public_key_tag_permissions(session, tag)) == 1, "The tag should have exactly 1 permission"

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    mapping = get_public_key_tag_permissions(session, tag)[0]
    fe_url = url(base_url, '/permissions/{}/revoke_tag/{}'.format(TAG_EDIT, mapping.mapping_id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body="",
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200
    tag = PublicKeyTag.get(session, name="tyler_was_here")
    assert len(get_public_key_tag_permissions(session, tag)) == 0, "The tag should have no permissions"
