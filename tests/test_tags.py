from datetime import date, timedelta
from urllib import urlencode

import pytest
from tornado.httpclient import HTTPError

from fixtures import fe_app as app
from fixtures import standard_graph, users, graph, groups, session, permissions  # noqa
from grouper.model_soup import Group, User
from grouper.models.public_key import PublicKey, _permission_intersection
from grouper.models.public_key_tag import PublicKeyTag
from grouper.models.permission import Permission
from grouper.constants import TAG_EDIT
from url_util import url
from util import get_users, get_groups, add_member, grant_permission
from collections import namedtuple


key_1 = ('ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDCUQeasspT/etEJR2WUoR+h2sMOQYbJgr0Q'
            'E+J8p97gEhmz107KWZ+3mbOwyIFzfWBcJZCEg9wy5Paj+YxbGONqbpXAhPdVQ2TLgxr41bNXvbcR'
            'AxZC+Q12UZywR4Klb2kungKz4qkcmSZzouaKK12UxzGB3xQ0N+3osKFj3xA1+B6HqrVreU19XdVo'
            'AJh0xLZwhw17/NDM+dAcEdMZ9V89KyjwjraXtOVfFhQF0EDF0ame8d6UkayGrAiXC2He0P2Cja+J'
            '371P27AlNLHFJij8WGxvcGGSeAxMLoVSDOOllLCYH5UieV8mNpX1kNe2LeA58ciZb0AXHaipSmCH'
            'gh/ some-comment')

key_2 = ("ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDF1DyXlqc40AVUgt/IO0GFcTniaoFt5qCUAeNVlva"
         "lMnsrRULIXkb0g1ds9P9/UI2jWr70ZYG7XieQX1F7NpzaDeUyPGCrLV1/ev1ZtUImCrDFfMznEjkcqB"
         "33mRe1rCFGKNVOYUviPE1yBdbfZBGUuJBX2GOXQQj9fU4Hiq3rAgOhz89717mt+qZxZllZ4mdyVEaMB"
         "WCwqAvl7Z5ecDjB+llFpBORTmsT8OZoGbZnJTIB1d9j0tSbegP17emE+g9fTrk4/ePmSIAKcSV3xj6h"
         "98AGesNibyu9eKVrroEptxX4crl0o95Me6B1/DCL632xrTO0a5mSmlF4cxCgjLj9 to/ key2")


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
            body=urlencode({'public_key': key_1}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    key = session.query(PublicKey).filter_by(user_id=user.id).scalar()

    # add SSH key
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': key_2}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    key2 = session.query(PublicKey).filter_by(public_key=key_2).scalar()

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag = PublicKeyTag.get(session, name="tyler_was_here")

    key = session.query(PublicKey).filter_by(public_key=key_1).scalar()
    assert key.tags() == [], "No public keys should have a tag unless it's been added to the key"

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "dont_tag_me_bro", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag = PublicKeyTag.get(session, name="dont_tag_me_bro")

    key = session.query(PublicKey).filter_by(public_key=key_1).scalar()
    assert key.tags() == [], "No public keys should have a tag unless it's been added to the key"

    fe_url = url(base_url, '/users/{}/public-key/{}/tag'.format(user.username, key.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here"}),
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200
    key = session.query(PublicKey).filter_by(public_key=key_1).scalar()
    assert len(key.tags()) == 1, "The key should have exactly 1 tag"
    assert key.tags()[0].name == "tyler_was_here"

    key2 = session.query(PublicKey).filter_by(public_key=key_2).scalar()
    assert len(key2.tags()) == 0, "Keys other than the one with the added tag should not gain tags"

@pytest.mark.gen_test
def test_remove_tag(users, http_client, base_url, session):

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    # add SSH key
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': key_1}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    key = session.query(PublicKey).filter_by(user_id=user.id).scalar()

    # add SSH key
    fe_url = url(base_url, '/users/{}/public-key/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'public_key': key_2}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    key2 = session.query(PublicKey).filter_by(public_key=key_2).scalar()

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag = PublicKeyTag.get(session, name="tyler_was_here")

    key = session.query(PublicKey).filter_by(public_key=key_1).scalar()
    assert key.tags() == [], "No public keys should have a tag unless it's been added to the key"

    fe_url = url(base_url, '/tags')
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "dont_tag_me_bro", "description": "Test Tag Please Ignore"}),
            headers={'X-Grouper-User': user.username})

    tag2 = PublicKeyTag.get(session, name="dont_tag_me_bro")

    key = session.query(PublicKey).filter_by(public_key=key_1).scalar()
    assert key.tags() == [], "No public keys should have a tag unless it's been added to the key"

    fe_url = url(base_url, '/users/{}/public-key/{}/tag'.format(user.username, key.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here"}),
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200
    key = session.query(PublicKey).filter_by(public_key=key_1).scalar()
    assert len(key.tags()) == 1, "The key should have exactly 1 tag"
    assert key.tags()[0].name == "tyler_was_here"

    key2 = session.query(PublicKey).filter_by(public_key=key_2).scalar()
    assert len(key2.tags()) == 0, "Keys other than the one with the added tag should not gain tags"

    fe_url = url(base_url, '/users/{}/public-key/{}/tag'.format(user.username, key2.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here"}),
            headers={'X-Grouper-User': user.username})

    key = session.query(PublicKey).filter_by(public_key=key_1).scalar()
    # Remove tag
    tag = PublicKeyTag.get(session, name="dont_tag_me_bro")
    fe_url = url(base_url, '/users/{}/public-key/{}/delete_tag/{}'.format(user.username, key.id, tag.id))
    with pytest.raises(HTTPError):
        resp = yield http_client.fetch(fe_url, method="POST",
                body="",
                headers={'X-Grouper-User': "oliver@a.co"})

    # Remove tag
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

    key = session.query(PublicKey).filter_by(public_key=key_1).scalar()
    assert len(key.tags()) == 0, "The key should have exactly 0 tags"

    key2 = session.query(PublicKey).filter_by(public_key=key_2).scalar()
    assert len(key2.tags()) == 1, "Removing a tag from one key should not affect other keys"

@pytest.mark.gen_test
def test_grant_permission_to_tag(users, http_client, base_url, session):

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
    perm = Permission.get(session, TAG_EDIT)
    assert len(tag.my_permissions()) == 1, "The tag should have exactly 1 permission"
    assert tag.my_permissions()[0].name == perm.name, "The tag's permission should be the one we added"
    assert tag.my_permissions()[0].argument == "*", "The tag's permission should be the one we added"

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
            body=urlencode({'public_key': key_1}),
            headers={'X-Grouper-User': user.username})

    key = session.query(PublicKey).filter_by(user_id=user.id).scalar()
    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    fe_url = url(base_url, '/users/{}/public-key/{}/tag'.format(user.username, key.id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'tagname': "tyler_was_here"}),
            headers={'X-Grouper-User': user.username})
    
    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    key = session.query(PublicKey).filter_by(user_id=user.id).scalar()
    assert len(key.my_permissions()) == 1, "The SSH Key should have only 1 permission"
    assert key.my_permissions()[0].name == TAG_EDIT, "The SSH key's permission should be TAG_EDIT"
    assert key.my_permissions()[0].argument == "prod", "The SSH key's permission argument should be restricted to the tag's argument"
    assert len(user.my_permissions()) > 1, "The user should have more than 1 permission"

def test_permission_intersection(standard_graph, session, users, groups, permissions):
    p = namedtuple("Permission", ["name", "argument"])
    astar = p("a", "*")
    ar = p("a", "r")
    at = p("a", "t")
    bstar = p("b", "*")
    br = p("b", "r")
    cstar = p("c", "*")
    cr = p("c", "r")

    assert _permission_intersection([astar], [astar]) == set([astar]), "The intersection of two identical lists should be the set of the contents of the list"
    assert _permission_intersection([ar], [ar]) == set([ar]), "The intersection of two identical lists should be the set of the contents of the list"
    assert _permission_intersection([astar], [ar]) == set([ar]), "The intersection of perm, * with perm, blah should be perm, blah"
    assert _permission_intersection([ar], [astar]) == set([ar]), "The intersection of perm, blah with perm, * should be perm, blah"

    assert _permission_intersection([astar], [bstar]) == set(), "The intersection of two disjoint lists should be the empty set"
    assert _permission_intersection([ar], [br]) == set(), "The intersection of two disjoint lists should be the empty set"
    assert _permission_intersection([ar], [at]) == set(), "The intersection of two disjoint lists should be the empty set"

    assert _permission_intersection([astar], [ar, at]) == set([ar, at]), "Wildcards should result in all applicable permissions being in the result"
    assert _permission_intersection([astar, ar, br, cr], [at, bstar, cr]) == set([at, br, cr]), "This should work"

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
    perm = Permission.get(session, TAG_EDIT)
    assert len(tag.my_permissions()) == 1, "The tag should have exactly 1 permission"

    user = session.query(User).filter_by(username="testuser@a.co").scalar()

    mapping = tag.my_permissions()[0]
    fe_url = url(base_url, '/permissions/{}/revoke_tag/{}'.format(TAG_EDIT, mapping.mapping_id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body="",
            headers={'X-Grouper-User': user.username})

    assert resp.code == 200
    tag = PublicKeyTag.get(session, name="tyler_was_here")
    assert len(tag.my_permissions()) == 0, "The tag should have no permissions"
