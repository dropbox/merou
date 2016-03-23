from grouper.fe.util import GrouperHandler
from grouper.models import AuditLog, Permission


class PermissionDisableAuditing(GrouperHandler):
    def post(self, user_id=None, name=None):
        if not self.current_user.permission_admin:
            return self.forbidden()

        permission = Permission.get(self.session, name)
        if not permission:
            return self.notfound()

        permission.disable_auditing()
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'disable_auditing',
                     'Disabled auditing.', on_permission_id=permission.id)

        # No explicit refresh because handler queries SQL.
        return self.redirect("/permissions/{}".format(permission.name))
