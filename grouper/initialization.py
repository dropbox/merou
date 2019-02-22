"""Setup functions common to all Grouper UIs."""

from typing import TYPE_CHECKING

from grouper.repositories.factory import RepositoryFactory
from grouper.services.factory import ServiceFactory
from grouper.usecases.factory import UseCaseFactory

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.models.base.session import Session
    from grouper.settings import Settings
    from typing import Optional


def create_usecase_factory(settings, session=None, graph=None):
    # type: (Settings, Optional[Session], Optional[GroupGraph]) -> UseCaseFactory
    """Create a UseCaseFactory, with optional injection of a Session and GroupGraph.

    Session and GroupGraph injection are supported primarily for tests.  If not injected, they will
    be created on demand.
    """
    repository_factory = RepositoryFactory(settings, session, graph)
    service_factory = ServiceFactory(repository_factory)
    return UseCaseFactory(service_factory)
