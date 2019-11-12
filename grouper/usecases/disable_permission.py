from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

from grouper.usecases.authorization import Authorization

if TYPE_CHECKING:
    from grouper.usecases.interfaces import (
        PermissionInterface,
        TransactionInterface,
        UserInterface,
    )
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
    )
    from typing import List


class DisablePermissionUI(metaclass=ABCMeta):
    """Abstract base class for UI for DisablePermission."""

    @abstractmethod
    def disabled_permission(self, name):
        # type: (str) -> None
        pass

    @abstractmethod
    def disable_permission_failed_existing_grants(
        self,
        name,  # type: str
        group_grants,  # type: List[GroupPermissionGrant]
        service_account_grants,  # type: List[ServiceAccountPermissionGrant]
    ):
        # type: (...) -> None
        pass

    @abstractmethod
    def disable_permission_failed_not_found(self, name):
        # type: (str) -> None
        pass

    @abstractmethod
    def disable_permission_failed_permission_denied(self, name):
        # type: (str) -> None
        pass

    @abstractmethod
    def disable_permission_failed_system_permission(self, name):
        # type: (str) -> None
        pass


class DisablePermission:
    """Disable a permission."""

    def __init__(
        self,
        actor,  # type: str
        ui,  # type: DisablePermissionUI
        permission_service,  # type: PermissionInterface
        user_service,  # type: UserInterface
        transaction_service,  # type: TransactionInterface
    ):
        # type: (...) -> None
        self.actor = actor
        self.ui = ui
        self.permission_service = permission_service
        self.user_service = user_service
        self.transaction_service = transaction_service

    def disable_permission(self, name):
        # type: (str) -> None
        """Disable a permission if it has no active grants.

        An active grant is defined as a permission grant to either an enabled group or an enabled
        service account.  If it has grants to disabled groups (group permission grants are
        preserved on group disable to allow restoring the group), those are ignored and will be
        deleted as part of disabling the permission.
        """
        if self.permission_service.is_system_permission(name):
            self.ui.disable_permission_failed_system_permission(name)
            return
        elif not self.permission_service.permission_exists(name):
            self.ui.disable_permission_failed_not_found(name)
            return
        elif not self.user_service.user_is_permission_admin(self.actor):
            self.ui.disable_permission_failed_permission_denied(name)
            return

        # Check if this permission is still granted to any active groups or service accounts.
        group_grants = self.permission_service.group_grants_for_permission(name)
        service_grants = self.permission_service.service_account_grants_for_permission(name)
        if group_grants or service_grants:
            self.ui.disable_permission_failed_existing_grants(name, group_grants, service_grants)
            return

        # Everything looks good.  Disable the permission.  Any remaining inactive grants will be
        # revoked here.
        authorization = Authorization(self.actor)
        with self.transaction_service.transaction():
            self.permission_service.disable_permission_and_revoke_grants(name, authorization)
        self.ui.disabled_permission(name)
