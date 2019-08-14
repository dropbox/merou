"""Setup functions common to all Grouper UIs."""

from typing import TYPE_CHECKING

from grouper.repositories.factory import (
    GraphRepositoryFactory,
    SessionFactory,
    SQLRepositoryFactory,
)
from grouper.services.factory import ServiceFactory
from grouper.usecases.factory import UseCaseFactory

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.plugin.proxy import PluginProxy
    from grouper.settings import Settings
    from typing import Optional


def create_graph_usecase_factory(
    settings,  # type: Settings
    plugins,  # type: PluginProxy
    session_factory=None,  # type: Optional[SessionFactory]
    graph=None,  # type: Optional[GroupGraph]
):
    # type: (...) -> UseCaseFactory
    """Create a graph-backed UseCaseFactory, with optional injection of a Session and GroupGraph.

    Session factory and graph injection is supported primarily for tests.  If not injected, they
    will be created on demand.
    """
    if not session_factory:
        session_factory = SessionFactory(settings)
    repository_factory = GraphRepositoryFactory(settings, plugins, session_factory, graph)
    service_factory = ServiceFactory(settings, plugins, repository_factory)
    return UseCaseFactory(settings, plugins, service_factory)


def create_sql_usecase_factory(settings, plugins, session_factory=None):
    # type: (Settings, PluginProxy, Optional[SessionFactory]) -> UseCaseFactory
    """Create a SQL-backed UseCaseFactory, with optional injection of a Session.

    Session factory injection is supported primarily for tests.  If not injected, it will be
    created on demand.
    """
    if not session_factory:
        session_factory = SessionFactory(settings)
    repository_factory = SQLRepositoryFactory(settings, plugins, session_factory)
    service_factory = ServiceFactory(settings, plugins, repository_factory)
    return UseCaseFactory(settings, plugins, service_factory)
