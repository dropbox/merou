from grouper.fe.util import GrouperHandler
from grouper.permissions import disable_permission_auditing, NoSuchPermission


class PermissionDisableAuditing(GrouperHandler):
    def post(self, user_id=None, name=None):
        if not self.current_user.permission_admin:
            return self.forbidden()

        try:
            disable_permission_auditing(self.session, name, self.current_user.id)
        except NoSuchPermission:
            return self.notfound()

        # No explicit refresh because handler queries SQL.
        return self.redirect("/permissions/{}".format(name))
