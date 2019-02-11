from typing import TYPE_CHECKING

from grouper.services.audit_log import AuditLogService
from grouper.services.permission import PermissionService
from grouper.services.transaction import TransactionService
from grouper.usecases.interfaces import ServiceFactoryInterface

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.repositories.factory import RepositoryFactory
    from grouper.usecases.interfaces import PermissionInterface, TransactionInterface


class ServiceFactory(ServiceFactoryInterface):
    """Construct backend services."""

    def __init__(self, session, repository_factory):
        # type: (Session, RepositoryFactory) -> None
        self.session = session
        self.repository_factory = repository_factory

    def create_permission_service(self):
        # type: () -> PermissionInterface
        audit_log = AuditLogService(self.session)
        permission_repository = self.repository_factory.create_permission_repository()
        return PermissionService(self.session, audit_log, permission_repository)

    def create_transaction_service(self):
        # type: () -> TransactionInterface
        return TransactionService(self.session)
