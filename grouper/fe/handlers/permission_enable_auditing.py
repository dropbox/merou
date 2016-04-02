from grouper.fe.util import GrouperHandler
from grouper.permissions import enable_permission_auditing, NoSuchPermission


class PermissionEnableAuditing(GrouperHandler):
    def post(self, name=None):
        if not self.current_user.permission_admin:
            return self.forbidden()

        try:
            enable_permission_auditing(self.session, name, self.current_user.id)
        except NoSuchPermission:
            return self.notfound()

        # No explicit refresh because handler queries SQL.
        return self.redirect("/permissions/{}".format(name))
