from urllib import urlencode

from mock import patch, MagicMock
import pytest
from wtforms import HiddenField, StringField, validators

from fixtures import fe_app as app  # noqa
from fixtures import standard_graph, users, graph, groups, session, permissions  # noqa
from grouper.fe.forms import SecretForm
from grouper.model_soup import User
from grouper.plugin import BasePlugin
from grouper.secret import Secret
from url_util import url


class TestSecretForm(SecretForm):
    path = StringField("Path", [
        validators.DataRequired(),
    ])
    type = HiddenField(default="TestSecret")


class TestSecret(Secret):

    form = TestSecretForm

    def __init__(self,
                 name,            # type: str
                 distribution,    # type: List[str]
                 owner,           # type: Group
                 notes,           # type: str
                 risk_level,      # type: int
                 risk_info,       # type: str
                 uses,            # type: str
                 path,            # type: str
                 new=False        # type: boolean
                 ):
        super(TestSecret, self).__init__(name, distribution, owner,
            notes, risk_level, risk_info, uses, new=new)
        self.path = path

    @classmethod
    def args_from_form(cls, session, form, new):
        ret = {
            "path": form.data["path"]
        }
        ret.update(Secret.args_from_form(session, form, new))
        return ret


class SecretTestPlugin(BasePlugin):

    def __init__(self, *args, **kwargs):
        self.secrets = {}

    def get_secret_forms(self):
        return [Secret, TestSecret]

    def commit_secret(self, session, secret, actor):
        self.secrets[secret.name] = secret

    def delete_secret(self, session, secret, actor):
        del self.secrets[secret.name]

    def get_secrets(self, session):
        return self.secrets


@pytest.mark.gen_test
def test_create_secret(users, groups, http_client, base_url, session):
    plugin = SecretTestPlugin()
    with patch("grouper.fe.handlers.secrets_view.get_secret_forms", lambda: [Secret, TestSecret]) as secret_forms:
        with patch("grouper.secret_plugin.get_plugins", lambda: [plugin]) as get_plugins:

            user = session.query(User).filter_by(username="testuser@a.co").scalar()

            fe_url = url(base_url, '/secrets')
            resp = yield http_client.fetch(fe_url, method="POST",
                    body=urlencode({
                        'name': "tyler_was_here",
                        'distribution': "Hello\r\nGoodbye",
                        'owner': groups["all-teams"].id,
                        'notes': "Test Note Please Ignore",
                        'risk_level': "3",
                        'risk_info': "super important secret",
                        'uses': "Used for testing the secrets code",
                        'type': "Secret",
                    }),
                    headers={'X-Grouper-User': user.username})
            assert resp.code == 200
            secrets = get_plugins()[0].get_secrets(session)
            assert len(secrets) == 1
            assert "tyler_was_here" in secrets
            secret = secrets["tyler_was_here"]
            assert secret.distribution == ["Hello", "Goodbye"]
            assert secret.owner.id == groups["all-teams"].id
            assert type(secret) == Secret

            fe_url = url(base_url, '/secrets')
            resp = yield http_client.fetch(fe_url, method="POST",
                    body=urlencode({
                        'name': "Super_Secret_TLS_Cert",
                        'distribution': "Hello\r\nGoodbye",
                        'owner': groups["all-teams"].id,
                        'notes': "Test Note Please Ignore",
                        'risk_level': "3",
                        'risk_info': "super important secret",
                        'uses': "Used for testing the secrets code",
                        'path': "/etc/nginx/ssl/",
                        'type': "TestSecret",
                    }),
                    headers={'X-Grouper-User': user.username})
            assert resp.code == 200
            secrets = get_plugins()[0].get_secrets(session)
            assert len(secrets) == 2
            assert "Super_Secret_TLS_Cert" in secrets
            secret = secrets["Super_Secret_TLS_Cert"]
            assert secret.distribution == ["Hello", "Goodbye"]
            assert secret.owner.id == groups["all-teams"].id
            assert secret.path == "/etc/nginx/ssl/"
            assert type(secret) == TestSecret


@pytest.mark.gen_test
def test_get_secret(users, groups, http_client, base_url, session):
    plugin = SecretTestPlugin()
    with patch("grouper.fe.handlers.secrets_view.get_secret_forms", lambda: [Secret, TestSecret]) as secret_forms:
        with patch("grouper.secret_plugin.get_plugins", lambda: [plugin]) as get_plugins:

            # Create Secret

            user = session.query(User).filter_by(username="testuser@a.co").scalar()

            fe_url = url(base_url, '/secrets')
            resp = yield http_client.fetch(fe_url, method="POST",
                    body=urlencode({
                        'name': "tyler_was_here",
                        'distribution': "Hello\r\nGoodbye",
                        'owner': groups["all-teams"].id,
                        'notes': "Test Note Please Ignore",
                        'risk_level': "3",
                        'risk_info': "super important secret",
                        'uses': "Used for testing the secrets code",
                        'type': "Secret",
                    }),
                    headers={'X-Grouper-User': user.username})
            assert resp.code == 200
            secrets = get_plugins()[0].get_secrets(session)
            assert len(secrets) == 1
            assert "tyler_was_here" in secrets
            secret = secrets["tyler_was_here"]
            assert secret.distribution == ["Hello", "Goodbye"]
            assert secret.owner.id == groups["all-teams"].id
            assert type(secret) == Secret

            fe_url = url(base_url, "/secrets/{}".format("tyler_was_here"))
            resp = yield http_client.fetch(fe_url, method="GET",
                                           headers={'X-Grouper-User': user.username})
            assert resp.code == 200


@pytest.mark.gen_test
def test_delete_secret(users, groups, http_client, base_url, session):
    plugin = SecretTestPlugin()
    with patch("grouper.fe.handlers.secrets_view.get_secret_forms", lambda: [Secret, TestSecret]) as secret_forms:
        with patch("grouper.secret_plugin.get_plugins", lambda: [plugin]) as get_plugins:

            # Create Secret

            user = session.query(User).filter_by(username="testuser@a.co").scalar()

            fe_url = url(base_url, '/secrets')
            resp = yield http_client.fetch(fe_url, method="POST",
                    body=urlencode({
                        'name': "tyler_was_here",
                        'distribution': "Hello\r\nGoodbye",
                        'owner': groups["all-teams"].id,
                        'notes': "Test Note Please Ignore",
                        'risk_level': "3",
                        'risk_info': "super important secret",
                        'uses': "Used for testing the secrets code",
                        'type': "Secret",
                    }),
                    headers={'X-Grouper-User': user.username})
            assert resp.code == 200
            secrets = get_plugins()[0].get_secrets(session)
            assert len(secrets) == 1
            assert "tyler_was_here" in secrets
            secret = secrets["tyler_was_here"]
            assert secret.distribution == ["Hello", "Goodbye"]
            assert secret.owner.id == groups["all-teams"].id
            assert type(secret) == Secret

            fe_url = url(base_url, "/secrets/{}".format("tyler_was_here"))
            resp = yield http_client.fetch(fe_url, method="DELETE",
                                           headers={'X-Grouper-User': user.username})
            assert resp.code == 200
            secrets = get_plugins()[0].get_secrets(session)
            assert len(secrets) == 0
            assert "tyler_was_here" not in secrets


@pytest.mark.gen_test
def test_edit_secret(users, groups, http_client, base_url, session):
    plugin = SecretTestPlugin()
    with patch("grouper.fe.handlers.secrets_view.get_secret_forms", lambda: [Secret, TestSecret]) as secret_forms:
        with patch("grouper.secret_plugin.get_plugins", lambda: [plugin]) as get_plugins:

            # Create Secret

            user = session.query(User).filter_by(username="testuser@a.co").scalar()

            fe_url = url(base_url, '/secrets')
            resp = yield http_client.fetch(fe_url, method="POST",
                    body=urlencode({
                        'name': "tyler_was_here",
                        'distribution': "Hello\r\nGoodbye",
                        'owner': groups["all-teams"].id,
                        'notes': "Test Note Please Ignore",
                        'risk_level': "3",
                        'risk_info': "super important secret",
                        'uses': "Used for testing the secrets code",
                        'type': "Secret",
                    }),
                    headers={'X-Grouper-User': user.username})
            assert resp.code == 200
            secrets = get_plugins()[0].get_secrets(session)
            assert len(secrets) == 1
            assert "tyler_was_here" in secrets
            secret = secrets["tyler_was_here"]
            assert secret.distribution == ["Hello", "Goodbye"]
            assert secret.owner.id == groups["all-teams"].id
            assert type(secret) == Secret

            fe_url = url(base_url, "/secrets/{}".format("tyler_was_here"))

            # Try to change secret name. Should not work
            resp = yield http_client.fetch(fe_url, method="POST",
                    body=urlencode({
                        'name': "lol",
                        'distribution': "USEAST\r\nUSWEST",
                        'owner': groups["all-teams"].id,
                        'notes': "Test Note Please Ignore",
                        'risk_level': "1",
                        'risk_info': "not important secret",
                        'uses': "Used for testing the secrets code",
                        'type': "Secret",
                    }),
                    headers={'X-Grouper-User': user.username})

            secrets = get_plugins()[0].get_secrets(session)
            assert len(secrets) == 1
            assert "tyler_was_here" in secrets

            # Try to change secret type. Also should not work
            resp = yield http_client.fetch(fe_url, method="POST",
                    body=urlencode({
                        'name': "tyler_was_here",
                        'distribution': "USEAST\r\nUSWEST",
                        'owner': groups["all-teams"].id,
                        'notes': "Test Note Please Ignore",
                        'risk_level': "1",
                        'risk_info': "not important secret",
                        'uses': "Used for testing the secrets code",
                        'type': "TestSecret",
                    }),
                    headers={'X-Grouper-User': user.username})

            assert resp.code == 200
            # Nothing should have changed because the above call should have failed
            secrets = get_plugins()[0].get_secrets(session)
            assert len(secrets) == 1
            assert "tyler_was_here" in secrets
            secret = secrets["tyler_was_here"]
            assert secret.distribution == ["Hello", "Goodbye"]
            assert secret.owner.id == groups["all-teams"].id
            assert type(secret) == Secret

            # Finally test the positive case
            resp = yield http_client.fetch(fe_url, method="POST",
                    body=urlencode({
                        'name': "tyler_was_here",
                        'distribution': "USEAST\r\nUSWEST",
                        'owner': groups["all-teams"].id,
                        'notes': "Test Note Please Ignore",
                        'risk_level': "1",
                        'risk_info': "not important secret",
                        'uses': "Used for testing the secrets code",
                        'type': "Secret",
                    }),
                    headers={'X-Grouper-User': user.username})

            assert resp.code == 200
            secrets = get_plugins()[0].get_secrets(session)
            assert len(secrets) == 1
            assert "tyler_was_here" in secrets
            secret = secrets["tyler_was_here"]
            assert secret.distribution == ["USEAST", "USWEST"]
            assert secret.owner.id == groups["all-teams"].id
            assert type(secret) == Secret
