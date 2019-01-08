from grouper.constants import AUDIT_MANAGER
from grouper.fe.util import GrouperHandler
from grouper.permissions import enable_permission_auditing, NoSuchPermission
from grouper.user_permissions import user_has_permission, user_is_permission_admin


class PermissionEnableAuditing(GrouperHandler):
    def post(self, name=None):
        if not (user_is_permission_admin(self.session, self.current_user) or
                user_has_permission(self.session, self.current_user, AUDIT_MANAGER)):
            return self.forbidden()

        try:
            enable_permission_auditing(self.session, name, self.current_user.id)
        except NoSuchPermission:
            return self.notfound()

        # No explicit refresh because handler queries SQL.
        return self.redirect("/permissions/{}".format(name))
