from typing import TYPE_CHECKING

from grouper.graph import Graph
from grouper.models.base.session import get_db_engine, Session
from grouper.repositories.audit_log import AuditLogRepository
from grouper.repositories.checkpoint import CheckpointRepository
from grouper.repositories.permission import GraphPermissionRepository, SQLPermissionRepository
from grouper.repositories.permission_grant import GraphPermissionGrantRepository
from grouper.repositories.transaction import TransactionRepository
from grouper.util import get_database_url

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.repositories.interfaces import PermissionRepository, PermissionGrantRepository
    from grouper.settings import Settings
    from typing import Optional


class RepositoryFactory(object):
    """Create repositories, which abstract storage away from the database layer.

    Dependency injection of the database session and graph is supported, primarily for testing, but
    normally the RepositoryFactory is responsible for creating the global session and graph and
    injecting them into all other repositories.

    Some use cases do not want a Session or GroupGraph (and in some cases cannot have a meaningful
    Session before they run, such as the command to set up the database).  The property methods in
    this factory lazily create those objects on demand so that the code doesn't run when those
    commands are instantiated.
    """

    def __init__(self, settings, session=None, graph=None):
        # type: (Settings, Optional[Session], Optional[GroupGraph]) -> None
        self.settings = settings
        self._session = session
        self._graph = graph

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
            db_engine = get_db_engine(get_database_url(self.settings))
            Session.configure(bind=db_engine)
            self._session = Session()
        return self._session

    def create_audit_log_repository(self):
        # type: () -> AuditLogRepository
        return AuditLogRepository(self.session)

    def create_checkpoint_repository(self):
        # type: () -> CheckpointRepository
        return CheckpointRepository(self.session)

    def create_permission_repository(self):
        # type: () -> PermissionRepository
        sql_permission_repository = SQLPermissionRepository(self.session)
        return GraphPermissionRepository(self.graph, sql_permission_repository)

    def create_permission_grant_repository(self):
        # type: () -> PermissionGrantRepository
        return GraphPermissionGrantRepository(self.graph)

    def create_transaction_repository(self):
        # type: () -> TransactionRepository
        return TransactionRepository(self.session)
