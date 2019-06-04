from typing import TYPE_CHECKING

from grouper.entities.user import User, UserMetadata
from tests.constants import SSH_KEY_1, SSH_KEY_2
from tests.util import key_to_public_key

if TYPE_CHECKING:
    from tests.setup import SetupTest


def test_sql_all_enabled_users(setup):
    # type: (SetupTest) -> None
    """Test the implementation that does not use the graph.

    This is not normally exercised by the usecase test suite, since the usecase expects to use the
    graph.  We're not currently using the pure SQL implementation, but expect to soon in the
    frontend, so make sure it doesn't bitrot.
    """
    with setup.transaction():
        setup.create_user("gary@a.co")
        setup.add_public_key_to_user(SSH_KEY_1, "gary@a.co")
        setup.add_public_key_to_user(SSH_KEY_2, "gary@a.co")
        setup.add_metadata_to_user("some-key", "some-value", "gary@a.co")
        setup.create_user("zorkian@a.co")
        setup.add_metadata_to_user("github_username", "zorkian", "zorkian@a.co")
        setup.add_metadata_to_user("shell", "/usr/bin/fish", "zorkian@a.co")
        setup.create_role_user("role-user@a.co")
        setup.create_service_account("service@svc.localhost", "some-group")
        setup.create_user("disabled@a.co")
        setup.session.flush()
        setup.disable_user("disabled@a.co")

    user_repository = setup.sql_repository_factory.create_user_repository()
    users = user_repository.all_enabled_users()

    assert users == {
        "gary@a.co": User(
            name="gary@a.co",
            enabled=True,
            role_user=False,
            metadata=[UserMetadata(key="some-key", value="some-value")],
            public_keys=[key_to_public_key(SSH_KEY_1), key_to_public_key(SSH_KEY_2)],
        ),
        "role-user@a.co": User(
            name="role-user@a.co", enabled=True, role_user=True, metadata=[], public_keys=[]
        ),
        "zorkian@a.co": User(
            name="zorkian@a.co",
            enabled=True,
            role_user=False,
            metadata=[
                UserMetadata(key="github_username", value="zorkian"),
                UserMetadata(key="shell", value="/usr/bin/fish"),
            ],
            public_keys=[],
        ),
    }
