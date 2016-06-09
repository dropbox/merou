from urllib import urlencode

from mock import patch
import pytest

from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa
from fixtures import fe_app as app  # noqa
from url_util import url

from grouper.constants import USER_METADATA_SHELL_KEY
from grouper.model_soup import User
from grouper.user_metadata import get_user_metadata_by_key


@pytest.mark.gen_test
def test_shell(session, users, http_client, base_url):
    with patch('grouper.fe.handlers.user_shell.settings') as mock_settings:
        mock_settings.shell = [['/bin/bash', 'bash'], ['/bin/zsh', 'zsh']]

        user = users['zorkian@a.co']
        assert not get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY)

        user = User.get(session, name=user.username)
        fe_url = url(base_url, '/users/{}/shell'.format(user.username))
        resp = yield http_client.fetch(fe_url, method="POST",
                body=urlencode({'shell': "/bin/bash"}),
                headers={'X-Grouper-User': user.username})
        assert resp.code == 200

        user = User.get(session, name=user.username)

        assert (get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY) is not None,
            "The user should have shell metadata")
        assert (get_user_metadata_by_key(session, user.id, 
                   USER_METADATA_SHELL_KEY).data_value == "/bin/bash")

        fe_url = url(base_url, '/users/{}/shell'.format(user.username))
        resp = yield http_client.fetch(fe_url, method="POST",
                body=urlencode({'shell': "/bin/fish"}),
                headers={'X-Grouper-User': user.username})
        assert resp.code == 200

        user = User.get(session, name=user.username)

        assert (get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY) is not None,
            "The user should have shell metadata")
        assert (get_user_metadata_by_key(session, user.id, 
                   USER_METADATA_SHELL_KEY).data_value == "/bin/bash")

        fe_url = url(base_url, '/users/{}/shell'.format(user.username))
        resp = yield http_client.fetch(fe_url, method="POST",
                body=urlencode({'shell': "/bin/zsh"}),
                headers={'X-Grouper-User': user.username})
        assert resp.code == 200

        user = User.get(session, name=user.username)

        assert (get_user_metadata_by_key(session, user.id, USER_METADATA_SHELL_KEY) is not None,
            "The user should have shell metadata")
        assert (get_user_metadata_by_key(session, user.id, 
                   USER_METADATA_SHELL_KEY).data_value == "/bin/zsh")
