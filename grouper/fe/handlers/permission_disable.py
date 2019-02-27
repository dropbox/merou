from grouper.fe.util import GrouperHandler
from grouper.usecases.disable_permission import DisablePermissionUI


class PermissionDisable(GrouperHandler, DisablePermissionUI):
    """Disable a permission via the browser UI."""

    def disabled_permission(self, name):
        # type: (str) -> None
        self.redirect("/permissions/{}".format(name))

    def disable_permission_failed_because_not_found(self, name):
        # type: (str) -> None
        return self.notfound()

    def disable_permission_failed_because_permission_denied(self, name):
        # type: (str) -> None
        return self.forbidden()

    def disable_permission_failed_because_system_permission(self, name):
        # type: (str) -> None
        return self.forbidden()

    def post(self, *args, **kwargs):
        # type: (*str, **str) -> None
        name = kwargs["name"]
        usecase = self.usecase_factory.create_disable_permission_usecase(
            self.current_user.username, self
        )
        usecase.disable_permission(name)
