from grouper.fe.util import GrouperHandler
from grouper.services.audit_log import AuditLogService
from grouper.services.permission import PermissionService
from grouper.usecases.disable_permission import DisablePermission, DisablePermissionUI


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

    def post(self, user_id=None, name=None):
        audit_log = AuditLogService(self.session)
        service = PermissionService(self.session, audit_log)
        usecase = DisablePermission(self.session, self.current_user.username, self, service)
        usecase.disable_permission(name)
