from typing import TYPE_CHECKING

from grouper.usecases.convert_user_to_service_account import ConvertUserToServiceAccount
from grouper.usecases.disable_permission import DisablePermission
from grouper.usecases.list_permissions import ListPermissions

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.usecases.convert_user_to_service_account import ConvertUserToServiceAccountUI
    from grouper.usecases.disable_permission import DisablePermissionUI
    from grouper.usecases.list_permissions import ListPermissionsUI


class UseCaseFactory(object):
    """Create use cases with dependency injection."""

    def __init__(self, service_factory):
        # type: (Session) -> None
        self.service_factory = service_factory

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

    def create_list_permissions_usecase(self, ui):
        # type: (ListPermissionsUI) -> ListPermissions
        permission_service = self.service_factory.create_permission_service()
        user_service = self.service_factory.create_user_service()
        return ListPermissions(ui, permission_service, user_service)
