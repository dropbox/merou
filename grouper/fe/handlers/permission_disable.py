from typing import TYPE_CHECKING

from grouper.fe.util import Alert, GrouperHandler
from grouper.usecases.disable_permission import DisablePermissionUI

if TYPE_CHECKING:
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
    )
    from typing import List


class PermissionDisable(GrouperHandler, DisablePermissionUI):
    """Disable a permission via the browser UI."""

    def disabled_permission(self, name):
        # type: (str) -> None
        self.redirect("/permissions/{}".format(name))

    def disable_permission_failed_existing_group_grants(self, name, grants):
        # type: (str, List[GroupPermissionGrant]) -> None
        """The permission view page will show the grants, so we don't include them in the error."""
        alert = Alert(
            "danger", "Permission cannot be disabled while it is still granted to some groups"
        )
        self.redirect("/permissions/{}".format(name), alerts=[alert])

    def disable_permission_failed_existing_service_account_grants(self, name, grants):
        # type: (str, List[ServiceAccountPermissionGrant]) -> None
        """The permission view page will show the grants, so we don't include them in the error."""
        alert = Alert(
            "danger",
            "Permission cannot be disabled while it is still granted to some service accounts",
        )
        self.redirect("/permissions/{}".format(name), alerts=[alert])

    def disable_permission_failed_not_found(self, name):
        # type: (str) -> None
        return self.notfound()

    def disable_permission_failed_permission_denied(self, name):
        # type: (str) -> None
        return self.forbidden()

    def disable_permission_failed_system_permission(self, name):
        # type: (str) -> None
        return self.forbidden()

    def post(self, *args, **kwargs):
        # type: (*str, **str) -> None
        name = kwargs["name"]
        usecase = self.usecase_factory.create_disable_permission_usecase(
            self.current_user.username, self
        )
        usecase.disable_permission(name)
