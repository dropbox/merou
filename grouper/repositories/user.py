from typing import TYPE_CHECKING

from grouper.entities.user import UserNotFoundException
from grouper.models.user import User

if TYPE_CHECKING:
    from grouper.models.base.session import Session


class UserRepository(object):
    """Storage layer for users."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def disable_user(self, name):
        # type: (str) -> None
        user = User.get(self.session, name=name)
        if not user:
            raise UserNotFoundException(name)
        user.enabled = False

    def user_is_enabled(self, name):
        # type: (str) -> bool
        user = User.get(self.session, name=name)
        if not user:
            raise UserNotFoundException(name)
        return user.enabled
