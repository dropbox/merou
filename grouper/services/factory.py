from typing import TYPE_CHECKING

from grouper.services.audit_log import AuditLogService
from grouper.services.group import GroupService
from grouper.services.group_request import GroupRequestService
from grouper.services.permission import PermissionService
from grouper.services.schema import SchemaService
from grouper.services.service_account import ServiceAccountService
from grouper.services.transaction import TransactionService
from grouper.services.user import UserService

if TYPE_CHECKING:
    from grouper.plugin import PluginProxy
    from grouper.repositories.interfaces import RepositoryFactory
    from grouper.settings import Settings
    from grouper.usecases.interfaces import (
        AuditLogInterface,
        GroupInterface,
        GroupRequestInterface,
        PermissionInterface,
        SchemaInterface,
        ServiceAccountInterface,
        TransactionInterface,
        UserInterface,
    )


class ServiceFactory:
    """Construct backend services."""

    def __init__(self, settings, plugins, repository_factory):
        # type: (Settings, PluginProxy, RepositoryFactory) -> None
        self.settings = settings
        self.plugins = plugins
        self.repository_factory = repository_factory

    def create_audit_log_service(self):
        # type: () -> AuditLogInterface
        audit_log_repository = self.repository_factory.create_audit_log_repository()
        return AuditLogService(audit_log_repository)

    def create_group_request_service(self):
        # type: () -> GroupRequestInterface
        audit_log_service = self.create_audit_log_service()
        group_request_repository = self.repository_factory.create_group_request_repository()
        return GroupRequestService(group_request_repository, audit_log_service)

    def create_group_service(self):
        # type: () -> GroupInterface
        group_repository = self.repository_factory.create_group_repository()
        permission_grant_repository = self.repository_factory.create_permission_grant_repository()
        return GroupService(group_repository, permission_grant_repository)

    def create_permission_service(self):
        # type: () -> PermissionInterface
        audit_log_service = self.create_audit_log_service()
        permission_repository = self.repository_factory.create_permission_repository()
        permission_grant_repository = self.repository_factory.create_permission_grant_repository()
        return PermissionService(
            audit_log_service, permission_repository, permission_grant_repository
        )

    def create_schema_service(self):
        # type: () -> SchemaInterface
        schema_repository = self.repository_factory.create_schema_repository()
        return SchemaService(schema_repository)

    def create_service_account_service(self):
        # type: () -> ServiceAccountInterface
        audit_log_service = self.create_audit_log_service()
        user_repository = self.repository_factory.create_user_repository()
        service_account_repository = self.repository_factory.create_service_account_repository()
        permission_grant_repository = self.repository_factory.create_permission_grant_repository()
        permission_repository = self.repository_factory.create_permission_repository()
        group_edge_repository = self.repository_factory.create_group_edge_repository()
        group_request_repository = self.repository_factory.create_group_request_repository()
        return ServiceAccountService(
            self.settings,
            self.plugins,
            user_repository,
            service_account_repository,
            permission_grant_repository,
            permission_repository,
            group_edge_repository,
            group_request_repository,
            audit_log_service,
        )

    def create_transaction_service(self):
        # type: () -> TransactionInterface
        transaction_repository = self.repository_factory.create_transaction_repository()
        checkpoint_repository = self.repository_factory.create_checkpoint_repository()
        return TransactionService(transaction_repository, checkpoint_repository)

    def create_user_service(self):
        # type: () -> UserInterface
        audit_log_service = self.create_audit_log_service()
        user_repository = self.repository_factory.create_user_repository()
        permission_repository = self.repository_factory.create_permission_repository()
        permission_grant_repository = self.repository_factory.create_permission_grant_repository()
        group_edge_repository = self.repository_factory.create_group_edge_repository()
        return UserService(
            user_repository,
            permission_repository,
            permission_grant_repository,
            group_edge_repository,
            audit_log_service,
        )
