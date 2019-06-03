from collections import defaultdict
from typing import TYPE_CHECKING

from grouper.entities.public_key import PublicKey
from grouper.entities.user import User, UserMetadata, UserNotFoundException
from grouper.models.public_key import PublicKey as SQLPublicKey
from grouper.models.user import User as SQLUser
from grouper.models.user_metadata import UserMetadata as SQLUserMetadata

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Dict, List


class UserRepository(object):
    """Storage layer for users."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def all_enabled_users(self):
        # type: () -> Dict[str, User]
        metadata = defaultdict(list)  # type: Dict[int, List[UserMetadata]]
        for user_metadata in self.session.query(SQLUserMetadata):
            metadata[user_metadata.user_id].append(
                UserMetadata(
                    key=user_metadata.data_key,
                    value=user_metadata.data_value,
                    modified_on=user_metadata.last_modified,
                )
            )

        public_keys = defaultdict(list)  # type: Dict[int, List[PublicKey]]
        for public_key in self.session.query(SQLPublicKey):
            public_keys[public_key.user_id].append(
                PublicKey(
                    public_key=public_key.public_key,
                    fingerprint=public_key.fingerprint,
                    fingerprint_sha256=public_key.fingerprint_sha256,
                    created_on=public_key.created_on,
                )
            )

        users = {}  # type: Dict[str, User]
        sql_users = self.session.query(SQLUser).filter(
            SQLUser.enabled == True, SQLUser.is_service_account == False
        )
        for user in sql_users:
            users[user.username] = User(
                name=user.username,
                enabled=user.enabled,
                role_user=user.role_user,
                metadata=metadata.get(user.id, []),
                public_keys=public_keys.get(user.id, []),
            )
        return users

    def disable_user(self, name):
        # type: (str) -> None
        user = SQLUser.get(self.session, name=name)
        if not user:
            raise UserNotFoundException(name)
        user.enabled = False

    def user_is_enabled(self, name):
        # type: (str) -> bool
        user = SQLUser.get(self.session, name=name)
        if not user:
            raise UserNotFoundException(name)
        return user.enabled
