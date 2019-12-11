from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.alerts import Alert
from grouper.fe.util import GrouperHandler
from grouper.usecases.disable_permission import DisablePermissionUI

if TYPE_CHECKING:
    from grouper.entities.permission_grant import (
        GroupPermissionGrant,
        ServiceAccountPermissionGrant,
    )
    from typing import Any, List


class PermissionDisable(GrouperHandler, DisablePermissionUI):
    """Disable a permission via the browser UI."""

    def disabled_permission(self, name: str) -> None:
        self.redirect("/permissions/{}".format(name))

    def disable_permission_failed_existing_grants(
        self,
        name: str,
        group_grants: List[GroupPermissionGrant],
        service_account_grants: List[ServiceAccountPermissionGrant],
    ) -> None:
        """The permission view page will show the grants, so we don't include them in the error."""
        alert = Alert(
            "danger",
            (
                "Permission cannot be disabled while it is still granted to some groups or"
                " service accounts"
            ),
        )
        self.redirect("/permissions/{}".format(name), alerts=[alert])

    def disable_permission_failed_not_found(self, name: str) -> None:
        return self.notfound()

    def disable_permission_failed_permission_denied(self, name: str) -> None:
        return self.forbidden()

    def disable_permission_failed_system_permission(self, name: str) -> None:
        return self.forbidden()

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")
        usecase = self.usecase_factory.create_disable_permission_usecase(
            self.current_user.username, self
        )
        usecase.disable_permission(name)
