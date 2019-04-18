"""Setup functions common to all Grouper UIs."""

from typing import TYPE_CHECKING

from grouper.repositories.factory import GraphRepositoryFactory, SQLRepositoryFactory
from grouper.services.factory import ServiceFactory
from grouper.usecases.factory import UseCaseFactory

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.models.base.session import Session
    from grouper.plugin.proxy import PluginProxy
    from grouper.settings import Settings
    from typing import Optional


def create_graph_usecase_factory(settings, plugins, session=None, graph=None):
    # type: (Settings, PluginProxy, Optional[Session], Optional[GroupGraph]) -> UseCaseFactory
    """Create a graph-backed UseCaseFactory, with optional injection of a Session and GroupGraph.

    Session and graph injection is supported primarily for tests.  If not injected, they will be
    created on demand.
    """
    repository_factory = GraphRepositoryFactory(settings, plugins, session, graph)
    service_factory = ServiceFactory(repository_factory)
    return UseCaseFactory(service_factory)


def create_sql_usecase_factory(settings, plugins, session=None):
    # type: (Settings, PluginProxy, Optional[Session]) -> UseCaseFactory
    """Create a SQL-backed UseCaseFactory, with optional injection of a Session.

    Session injection is supported primarily for tests.  If not injected, it will be created on
    demand.
    """
    repository_factory = SQLRepositoryFactory(settings, plugins, session)
    service_factory = ServiceFactory(repository_factory)
    return UseCaseFactory(service_factory)
