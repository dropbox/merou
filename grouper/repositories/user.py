from typing import TYPE_CHECKING

from grouper.entities.user import User, UserNotFoundException
from grouper.models.user import User as SQLUser
from grouper.repositories.interfaces import UserRepository

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.models.base.session import Session
    from typing import Dict


class GraphUserRepository(UserRepository):
    """Graph-aware storage layer for users."""

    def __init__(self, graph, repository):
        # type: (GroupGraph, UserRepository) -> None
        self.graph = graph
        self.repository = repository

    def all_users(self):
        # type: () -> Dict[str, User]
        return self.graph.all_user_metadata()

    def disable_user(self, user):
        # type: (str) -> None
        self.repository.disable_user(user)

    def user_exists(self, name):
        # type: (str) -> bool
        return self.repository.user_exists(name)

    def user_is_enabled(self, name):
        # type: (str) -> bool
        """Return whether a user is enabled.

        TODO(rra): This checks the underlying data store, not the graph, even though this
        information is in the graph, because the convert_user_to_service_account usecase disables a
        user and then immediately checks whether the user is disabled, and we don't want to force a
        graph refresh in the middle of that usecase.  This indicates a deeper underlying problem
        where some usecases need to use SQL repositories rather than the graph, which we're
        deferring for future work when we significantly reorganize how Grouper uses the graph.
        """
        return self.repository.user_is_enabled(name)


class SQLUserRepository(UserRepository):
    """SQL storage layer for users."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def all_users(self):
        # type: () -> Dict[str, User]
        raise NotImplementedError()

    def disable_user(self, name):
        # type: (str) -> None
        user = SQLUser.get(self.session, name=name)
        if not user:
            raise UserNotFoundException(name)
        user.enabled = False

    def user_exists(self, name):
        # type: (str) -> bool
        return SQLUser.get(self.session, name=name) is not None

    def user_is_enabled(self, name):
        # type: (str) -> bool
        user = SQLUser.get(self.session, name=name)
        if not user:
            raise UserNotFoundException(name)
        return user.enabled
