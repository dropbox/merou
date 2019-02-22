from typing import TYPE_CHECKING

from grouper.services.audit_log import AuditLogService
from grouper.services.permission import PermissionService
from grouper.services.transaction import TransactionService
from grouper.services.user import UserService
from grouper.usecases.interfaces import ServiceFactoryInterface

if TYPE_CHECKING:
    from grouper.repositories.factory import RepositoryFactory
    from grouper.usecases.interfaces import (
        PermissionInterface,
        TransactionInterface,
        UserInterface,
    )


class ServiceFactory(ServiceFactoryInterface):
    """Construct backend services."""

    def __init__(self, repository_factory):
        # type: (RepositoryFactory) -> None
        self.repository_factory = repository_factory

    def create_permission_service(self):
        # type: () -> PermissionInterface
        audit_log_repository = self.repository_factory.create_audit_log_repository()
        audit_log_service = AuditLogService(audit_log_repository)
        permission_repository = self.repository_factory.create_permission_repository()
        return PermissionService(audit_log_service, permission_repository)

    def create_transaction_service(self):
        # type: () -> TransactionInterface
        transaction_repository = self.repository_factory.create_transaction_repository()
        checkpoint_repository = self.repository_factory.create_checkpoint_repository()
        return TransactionService(transaction_repository, checkpoint_repository)

    def create_user_service(self):
        # type: () -> UserInterface
        permission_grant_repository = self.repository_factory.create_permission_grant_repository()
        return UserService(permission_grant_repository)
