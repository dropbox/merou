from typing import TYPE_CHECKING

from grouper.usecases.convert_user_to_service_account import ConvertUserToServiceAccount
from grouper.usecases.create_service_account import CreateServiceAccount
from grouper.usecases.disable_permission import DisablePermission
from grouper.usecases.dump_schema import DumpSchema
from grouper.usecases.initialize_schema import InitializeSchema
from grouper.usecases.list_grants import ListGrants
from grouper.usecases.list_permissions import ListPermissions
from grouper.usecases.list_users import ListUsers
from grouper.usecases.view_permission import ViewPermission

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.plugin.proxy import PluginProxy
    from grouper.settings import Settings
    from grouper.usecases.create_service_account import CreateServiceAccountUI
    from grouper.usecases.convert_user_to_service_account import ConvertUserToServiceAccountUI
    from grouper.usecases.disable_permission import DisablePermissionUI
    from grouper.usecases.dump_schema import DumpSchemaUI
    from grouper.usecases.list_grants import ListGrantsUI
    from grouper.usecases.list_users import ListUsersUI
    from grouper.usecases.list_permissions import ListPermissionsUI
    from grouper.usecases.view_permission import ViewPermissionUI


class UseCaseFactory(object):
    """Create use cases with dependency injection."""

    def __init__(self, settings, plugins, service_factory):
        # type: (Settings, PluginProxy, Session) -> None
        self.settings = settings
        self.plugins = plugins
        self.service_factory = service_factory

    def create_create_service_account_usecase(self, actor, ui):
        # type: (str, CreateServiceAccountUI) -> CreateServiceAccount
        service_account_service = self.service_factory.create_service_account_service()
        user_service = self.service_factory.create_user_service()
        transaction_service = self.service_factory.create_transaction_service()
        return CreateServiceAccount(
            actor,
            ui,
            self.settings,
            self.plugins,
            service_account_service,
            user_service,
            transaction_service,
        )

    def create_convert_user_to_service_account_usecase(self, actor, ui):
        # type: (str, ConvertUserToServiceAccountUI) -> ConvertUserToServiceAccount
        user_service = self.service_factory.create_user_service()
        service_account_service = self.service_factory.create_service_account_service()
        group_request_service = self.service_factory.create_group_request_service()
        transaction_service = self.service_factory.create_transaction_service()
        return ConvertUserToServiceAccount(
            actor,
            ui,
            user_service,
            service_account_service,
            group_request_service,
            transaction_service,
        )

    def create_disable_permission_usecase(self, actor, ui):
        # type: (str, DisablePermissionUI) -> DisablePermission
        permission_service = self.service_factory.create_permission_service()
        transaction_service = self.service_factory.create_transaction_service()
        user_service = self.service_factory.create_user_service()
        return DisablePermission(actor, ui, permission_service, user_service, transaction_service)

    def create_dump_schema_usecase(self, ui):
        # type: (DumpSchemaUI) -> DumpSchema
        schema_service = self.service_factory.create_schema_service()
        return DumpSchema(ui, schema_service)

    def create_list_grants_usecase(self, ui):
        # type: (ListGrantsUI) -> ListGrants
        permission_service = self.service_factory.create_permission_service()
        return ListGrants(ui, permission_service)

    def create_list_permissions_usecase(self, ui):
        # type: (ListPermissionsUI) -> ListPermissions
        permission_service = self.service_factory.create_permission_service()
        user_service = self.service_factory.create_user_service()
        return ListPermissions(ui, permission_service, user_service)

    def create_list_users_usecase(self, ui):
        # type: (ListUsersUI) -> ListUsers
        user_service = self.service_factory.create_user_service()
        return ListUsers(ui, user_service)

    def create_initialize_schema_usecase(self):
        # type: () -> InitializeSchema
        schema_service = self.service_factory.create_schema_service()
        group_service = self.service_factory.create_group_service()
        permission_service = self.service_factory.create_permission_service()
        transaction_service = self.service_factory.create_transaction_service()
        return InitializeSchema(
            self.settings, schema_service, group_service, permission_service, transaction_service
        )

    def create_view_permission_usecase(self, ui):
        # type: (ViewPermissionUI) -> ViewPermission
        permission_service = self.service_factory.create_permission_service()
        user_service = self.service_factory.create_user_service()
        audit_log_service = self.service_factory.create_audit_log_service()
        return ViewPermission(ui, permission_service, user_service, audit_log_service)
