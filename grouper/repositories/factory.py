from typing import TYPE_CHECKING

from grouper.graph import Graph
from grouper.models.base.session import DbEngineManager, Session
from grouper.repositories.audit_log import AuditLogRepository
from grouper.repositories.checkpoint import CheckpointRepository
from grouper.repositories.group import GroupRepository
from grouper.repositories.group_edge import GraphGroupEdgeRepository, SQLGroupEdgeRepository
from grouper.repositories.group_request import GroupRequestRepository
from grouper.repositories.interfaces import RepositoryFactory
from grouper.repositories.permission import GraphPermissionRepository, SQLPermissionRepository
from grouper.repositories.permission_grant import (
    GraphPermissionGrantRepository,
    SQLPermissionGrantRepository,
)
from grouper.repositories.schema import SchemaRepository
from grouper.repositories.service_account import ServiceAccountRepository
from grouper.repositories.transaction import TransactionRepository
from grouper.repositories.user import GraphUserRepository, SQLUserRepository

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.plugin.proxy import PluginProxy
    from grouper.repositories.interfaces import (
        GroupEdgeRepository,
        PermissionRepository,
        PermissionGrantRepository,
        UserRepository,
    )
    from grouper.settings import Settings
    from typing import Optional


class SessionFactory:
    """Create database sessions.

    Eventually this will be used only by the RepositoryFactory to get a session to inject into
    other repositories.  For now, it's also used by legacy code that hasn't been rewritten as
    usecases.
    """

    def __init__(self, settings):
        # type: (Settings) -> None
        self.settings = settings
        self._db_engine_manager = DbEngineManager()

    def create_session(self):
        # type: () -> Session
        db_engine = self._db_engine_manager.get_db_engine(self.settings.database)
        Session.configure(bind=db_engine)
        return Session()


class SingletonSessionFactory(SessionFactory):
    """Always returns the database session with which it was initialized.

    This is used primarily for testing to force all parts of a test case to use the same session,
    which avoids some data desynchronization between sessions when using a persistent store.  It is
    also used in legacy code when session injection is needed.
    """

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def create_session(self):
        # type: () -> Session
        return self.session


class GraphRepositoryFactory(RepositoryFactory):
    """Create repositories, which abstract storage away from the database layer.

    This factory injects a database session and a graph and prefers the graph-aware versions of the
    repositories.

    Dependency injection of the database session and graph is supported, primarily for testing, but
    normally the GraphRepositoryFactory is responsible for creating the global session and graph
    and injecting them into all other repositories.

    Some use cases do not want a Session or GroupGraph (and in some cases cannot have a meaningful
    Session before they run, such as the command to set up the database).  The property methods in
    this factory lazily create those objects on demand so that the code doesn't run when those
    commands are instantiated.
    """

    def __init__(self, settings, plugins, session_factory, graph=None):
        # type: (Settings, PluginProxy, SessionFactory, Optional[GroupGraph]) -> None
        self.settings = settings
        self.plugins = plugins
        self.session_factory = session_factory
        self._graph = graph
        self._session = None  # type: Optional[Session]

    @property
    def graph(self):
        # type: () -> GroupGraph
        if not self._graph:
            self._graph = Graph()
        return self._graph

    @property
    def session(self):
        # type: () -> Session
        if not self._session:
            self._session = self.session_factory.create_session()
        return self._session

    def create_audit_log_repository(self):
        # type: () -> AuditLogRepository
        return AuditLogRepository(self.session, self.plugins)

    def create_checkpoint_repository(self):
        # type: () -> CheckpointRepository
        return CheckpointRepository(self.session)

    def create_group_edge_repository(self):
        # type: () -> GroupEdgeRepository
        return GraphGroupEdgeRepository(self.graph)

    def create_group_repository(self):
        # type: () -> GroupRepository
        return GroupRepository(self.session)

    def create_group_request_repository(self):
        # type: () -> GroupRequestRepository
        return GroupRequestRepository(self.session)

    def create_permission_repository(self):
        # type: () -> PermissionRepository
        sql_permission_repository = SQLPermissionRepository(self.session)
        return GraphPermissionRepository(self.graph, sql_permission_repository)

    def create_permission_grant_repository(self):
        # type: () -> PermissionGrantRepository
        sql_permission_grant_repository = SQLPermissionGrantRepository(self.session)
        return GraphPermissionGrantRepository(self.graph, sql_permission_grant_repository)

    def create_service_account_repository(self):
        # type: () -> ServiceAccountRepository
        return ServiceAccountRepository(self.session)

    def create_schema_repository(self):
        # type: () -> SchemaRepository
        return SchemaRepository(self.settings)

    def create_transaction_repository(self):
        # type: () -> TransactionRepository
        return TransactionRepository(self.session)

    def create_user_repository(self):
        # type: () -> UserRepository
        sql_user_repository = SQLUserRepository(self.session)
        return GraphUserRepository(self.graph, sql_user_repository)


class SQLRepositoryFactory(RepositoryFactory):
    """Create repositories, which abstract storage away from the database layer.

    This factory injects only a database session and does not use graph-aware repositories.
    Dependency injection of the database session is supported, primarily for testing, but normally
    the SQLRepositoryFactory is responsible for creating the global session injecting
    it into all other repositories.

    Some use cases do not want a Session (and in some cases cannot have a meaningful Session before
    they run, such as the command to set up the database).  The property methods in this factory
    lazily create those objects on demand so that the code doesn't run when those commands are
    instantiated.
    """

    def __init__(self, settings, plugins, session_factory):
        # type: (Settings, PluginProxy, SessionFactory) -> None
        self.settings = settings
        self.plugins = plugins
        self.session_factory = session_factory
        self._session = None  # type: Optional[Session]

    @property
    def session(self):
        # type: () -> Session
        if not self._session:
            self._session = self.session_factory.create_session()
        return self._session

    def create_audit_log_repository(self):
        # type: () -> AuditLogRepository
        return AuditLogRepository(self.session, self.plugins)

    def create_checkpoint_repository(self):
        # type: () -> CheckpointRepository
        return CheckpointRepository(self.session)

    def create_group_edge_repository(self):
        # type: () -> GroupEdgeRepository
        return SQLGroupEdgeRepository(self.session)

    def create_group_repository(self):
        # type: () -> GroupRepository
        return GroupRepository(self.session)

    def create_group_request_repository(self):
        # type: () -> GroupRequestRepository
        return GroupRequestRepository(self.session)

    def create_permission_repository(self):
        # type: () -> PermissionRepository
        return SQLPermissionRepository(self.session)

    def create_permission_grant_repository(self):
        # type: () -> PermissionGrantRepository
        return SQLPermissionGrantRepository(self.session)

    def create_schema_repository(self):
        # type: () -> SchemaRepository
        return SchemaRepository(self.settings)

    def create_service_account_repository(self):
        # type: () -> ServiceAccountRepository
        return ServiceAccountRepository(self.session)

    def create_transaction_repository(self):
        # type: () -> TransactionRepository
        return TransactionRepository(self.session)

    def create_user_repository(self):
        # type: () -> UserRepository
        return SQLUserRepository(self.session)
