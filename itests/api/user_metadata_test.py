from typing import TYPE_CHECKING

from groupy.client import Groupy

from itests.setup import api_server
from tests.constants import SSH_KEY_1, SSH_KEY_2
from tests.util import key_to_public_key

if TYPE_CHECKING:
    from py._path.local import LocalPath
    from tests.setup import SetupTest


def test_user_metadata(tmpdir, setup):
    # type: (LocalPath, SetupTest) -> None
    with setup.transaction():
        setup.create_user("gary@a.co")
        setup.add_public_key_to_user(SSH_KEY_1, "gary@a.co")
        setup.add_public_key_to_user(SSH_KEY_2, "gary@a.co")
        setup.add_metadata_to_user("some-key", "some-value", "gary@a.co")
        setup.create_user("zorkian@a.co")
        setup.add_metadata_to_user("github_username", "zorkian", "zorkian@a.co")
        setup.add_metadata_to_user("shell", "/usr/bin/fish", "zorkian@a.co")
        setup.create_user("disabled@a.co")
        setup.session.flush()
        setup.disable_user("disabled@a.co")
        setup.create_role_user("role-user@a.co", "Some role user")
        setup.create_service_account("service@svc.localhost", "some-group")

    ssh_key_1 = key_to_public_key(SSH_KEY_1)
    ssh_key_2 = key_to_public_key(SSH_KEY_2)
    expected = {
        "gary@a.co": {
            "role_user": False,
            "metadata": {"some-key": "some-value"},
            "public_keys": [
                {
                    "public_key": ssh_key_1.public_key,
                    "fingerprint": ssh_key_1.fingerprint,
                    "fingerprint_sha256": ssh_key_1.fingerprint_sha256,
                },
                {
                    "public_key": ssh_key_2.public_key,
                    "fingerprint": ssh_key_2.fingerprint,
                    "fingerprint_sha256": ssh_key_2.fingerprint_sha256,
                },
            ],
        },
        "role-user@a.co": {"role_user": True, "metadata": {}, "public_keys": []},
        "zorkian@a.co": {
            "role_user": False,
            "metadata": {"github_username": "zorkian", "shell": "/usr/bin/fish"},
            "public_keys": [],
        },
    }

    with api_server(tmpdir) as api_url:
        api_client = Groupy(api_url)
        result = api_client._fetch("/user-metadata")
        assert result["status"] == "ok"
        assert result["data"]["users"] == expected
