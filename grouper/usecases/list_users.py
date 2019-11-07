from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grouper.entities.user import User
    from grouper.usecases.interfaces import UserInterface
    from typing import Dict


class ListUsersUI(metaclass=ABCMeta):
    """Abstract base class for UI for ListUserMetadata."""

    @abstractmethod
    def listed_users(self, users):
        # type: (Dict[str, User]) -> None
        pass


class ListUsers:
    """List all users."""

    def __init__(self, ui, user_service):
        # type: (ListUsersUI, UserInterface) -> None
        self.ui = ui
        self.user_service = user_service

    def list_users(self):
        # type: () -> None
        users = self.user_service.all_users()
        self.ui.listed_users(users)
