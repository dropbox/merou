from grouper.fe.util import GrouperHandler
from grouper.util import matches_glob
from grouper.models.audit_log import AuditLog
from grouper.models.counter import Counter
from grouper.models.permission_map import PermissionMap


class PermissionsRevoke(GrouperHandler):
    def get(self, name=None, mapping_id=None):
        grantable = self.current_user.my_grantable_permissions()
        if not grantable:
            return self.forbidden()

        mapping = PermissionMap.get(self.session, id=mapping_id)
        if not mapping:
            return self.notfound()

        allowed = False
        for perm in grantable:
            if perm[0].name == mapping.permission.name:
                if matches_glob(perm[1], mapping.argument):
                    allowed = True
        if not allowed:
            return self.forbidden()

        self.render("permission-revoke.html", mapping=mapping)

    def post(self, name=None, mapping_id=None):
        grantable = self.current_user.my_grantable_permissions()
        if not grantable:
            return self.forbidden()

        mapping = PermissionMap.get(self.session, id=mapping_id)
        if not mapping:
            return self.notfound()

        allowed = False
        for perm in grantable:
            if perm[0].name == mapping.permission.name:
                if matches_glob(perm[1], mapping.argument):
                    allowed = True
        if not allowed:
            return self.forbidden()

        permission = mapping.permission
        group = mapping.group

        mapping.delete(self.session)
        Counter.incr(self.session, "updates")
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'revoke_permission',
                     'Revoked permission with argument: {}'.format(mapping.argument),
                     on_group_id=group.id, on_permission_id=permission.id)

        return self.redirect('/groups/{}?refresh=yes'.format(group.name))
