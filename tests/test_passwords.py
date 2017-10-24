from urllib import urlencode

import pytest
from tornado.httpclient import HTTPError

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from grouper.model_soup import User
from grouper.user_password import PasswordAlreadyExists, add_new_user_password, delete_user_password, user_passwords
from url_util import url

TEST_PASSWORD = "test_password_please_ignore"


def test_passwords(session, users):
    user = users['zorkian@a.co']

    add_new_user_password(session, "test", TEST_PASSWORD, user.id)
    assert len(user_passwords(session, user)) == 1, "The user should only have a single password"
    password = user_passwords(session, user)[0]
    assert password.name == "test", "The password should have the name we gave it"
    assert password.password_hash != TEST_PASSWORD, "The password should not be what is passed in"
    assert password.check_password(TEST_PASSWORD), "The password should validate when given the same password"
    assert not password.check_password("sadfjhsdf"), "Incorrect passwords should fail"
    
    add_new_user_password(session, "test2", TEST_PASSWORD, user.id)
    assert len(user_passwords(session, user)) == 2, "The user should have 2 passwords"
    password2 = user_passwords(session, user)[1]
    assert password2.name == "test2", "The password should have the name we gave it"
    assert password2.password_hash != TEST_PASSWORD, "The password should not be what is passed in"
    assert password2.check_password(TEST_PASSWORD), "The password should validate when given the same password"
    assert not password2.check_password("sadfjhsdf"), "Incorrect passwords should fail"

    with pytest.raises(PasswordAlreadyExists):
        add_new_user_password(session, "test", TEST_PASSWORD, user.id)

    session.rollback()

    # Technically there's a very very very small O(1/2^160) chance that this will fail for a correct implementation
    assert password.password_hash != password2.password_hash, "2 passwords that are identical should hash differently because of the salts"

    delete_user_password(session, "test", user.id)
    assert len(user_passwords(session, user)) == 1, "The user should only have a single password"
    assert user_passwords(session, user)[0].name == "test2", "The password named test should have been deleted"

@pytest.mark.gen_test
def test_fe_password_add(session, users, http_client, base_url):
    user = users['zorkian@a.co']

    fe_url = url(base_url, '/users/{}/passwords/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'name': "test", "password": TEST_PASSWORD}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = session.query(User).filter_by(name="zorkian@a.co").scalar()
    assert len(user_passwords(session, user)) == 1, "The user should have a password now"
    assert user_passwords(session, user)[0].name == "test", "The password should have the name given"
    assert user_passwords(session, user)[0].password_hash != TEST_PASSWORD, "The password should not be available as plain text"

    with pytest.raises(HTTPError):
        fe_url = url(base_url, '/users/{}/passwords/add'.format(user.username))
        resp = yield http_client.fetch(fe_url, method="POST",
                body=urlencode({'name': "test", "password": TEST_PASSWORD}),
                headers={'X-Grouper-User': "testuser@a.co"})

    fe_url = url(base_url, '/users/{}/passwords/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'name': "test", "password": TEST_PASSWORD}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = session.query(User).filter_by(name="zorkian@a.co").scalar()
    assert len(user_passwords(session, user)) == 1, "Adding a password with the same name should fail"

    user = session.query(User).filter_by(name="testuser@a.co").scalar()
    fe_url = url(base_url, '/users/{}/passwords/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'name': "test", "password": TEST_PASSWORD}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = session.query(User).filter_by(name="testuser@a.co").scalar()
    assert len(user_passwords(session, user)) == 1, "The user should have a password now (duplicate names are permitted for distinct users)"
    assert user_passwords(session, user)[0].name == "test", "The password should have the name given"
    assert user_passwords(session, user)[0].password_hash != TEST_PASSWORD, "The password should not be available as plain text"

@pytest.mark.gen_test
def test_fe_password_delete(session, users, http_client, base_url):
    user = users['zorkian@a.co']

    fe_url = url(base_url, '/users/{}/passwords/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'name': "test", "password": TEST_PASSWORD}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = session.query(User).filter_by(name="zorkian@a.co").scalar()
    assert len(user_passwords(session, user)) == 1, "The user should have a password now"
    assert user_passwords(session, user)[0].name == "test", "The password should have the name given"
    assert user_passwords(session, user)[0].password_hash != TEST_PASSWORD, "The password should not be available as plain text"

    user = session.query(User).filter_by(name="testuser@a.co").scalar()
    fe_url = url(base_url, '/users/{}/passwords/add'.format(user.username))
    resp = yield http_client.fetch(fe_url, method="POST",
            body=urlencode({'name': "test", "password": TEST_PASSWORD}),
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = session.query(User).filter_by(name="testuser@a.co").scalar()
    assert len(user_passwords(session, user)) == 1, "The user should have a password now (duplicate names are permitted for distinct users)"
    assert user_passwords(session, user)[0].name == "test", "The password should have the name given"
    assert user_passwords(session, user)[0].password_hash != TEST_PASSWORD, "The password should not be available as plain text"

    with pytest.raises(HTTPError):
        user = session.query(User).filter_by(name="zorkian@a.co").scalar()
        fe_url = url(base_url, '/users/{}/passwords/{}/delete'.format(user.username, user_passwords(session, user)[0].id))
        resp = yield http_client.fetch(fe_url, method="POST",
                body="",
                headers={'X-Grouper-User': "testuser@a.co"})

    user = session.query(User).filter_by(name="zorkian@a.co").scalar()
    fe_url = url(base_url, '/users/{}/passwords/{}/delete'.format(user.username, user_passwords(session, user)[0].id))
    resp = yield http_client.fetch(fe_url, method="POST",
            body="",
            headers={'X-Grouper-User': user.username})
    assert resp.code == 200

    user = session.query(User).filter_by(name="zorkian@a.co").scalar()
    assert len(user_passwords(session, user)) == 0, "The password should have been deleted"
    user = session.query(User).filter_by(name="testuser@a.co").scalar()
    assert len(user_passwords(session, user)) == 1, "Other user's passwords should not have been deleted"

