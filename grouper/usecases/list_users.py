from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from six import with_metaclass

if TYPE_CHECKING:
    from grouper.entities.user import User
    from grouper.usecases.interfaces import UserInterface
    from typing import Dict


class ListUsersUI(with_metaclass(ABCMeta, object)):
    """Abstract base class for UI for ListUserMetadata."""

    @abstractmethod
    def listed_users(self, users):
        # type: (Dict[str, User]) -> None
        pass


class ListUsers(object):
    """List all users."""

    def __init__(self, ui, user_service):
        # type: (ListUsersUI, UserInterface) -> None
        self.ui = ui
        self.user_service = user_service

    def list_users(self):
        # type: () -> None
        users = self.user_service.all_enabled_users()
        self.ui.listed_users(users)
