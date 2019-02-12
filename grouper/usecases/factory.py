from typing import TYPE_CHECKING

from grouper.usecases.disable_permission import DisablePermission

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.usecases.disable_permission import DisablePermissionUI


class UseCaseFactory(object):
    """Create use cases with dependency injection."""

    def __init__(self, service_factory):
        # type: (Session) -> None
        self.service_factory = service_factory

    def create_disable_permission_usecase(self, actor, ui):
        # type: (str, DisablePermissionUI) -> DisablePermission
        permission_service = self.service_factory.create_permission_service()
        transaction_service = self.service_factory.create_transaction_service()
        return DisablePermission(actor, ui, permission_service, transaction_service)
