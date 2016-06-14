from grouper.fe.util import GrouperHandler
from grouper.group import user_is_owner_of_group
from grouper.models.audit_log import AuditLog
from grouper.models.counter import Counter
from grouper.models.permission_map import PermissionMap
from grouper.user_permissions import user_grantable_permissions
from grouper.util import matches_glob


class PermissionsRevoke(GrouperHandler):

    def get(self, name=None, mapping_id=None):
        grantable = user_grantable_permissions(self.session, self.current_user)
        mapping = PermissionMap.get(self.session, id=mapping_id)
        user_is_owner = mapping and user_is_owner_of_group(self.session, mapping.group,
            self.current_user)
        if not grantable and not user_is_owner:
            return self.forbidden()

        if not mapping:
            return self.notfound()

        allowed = user_is_owner
        for perm in grantable:
            if perm[0].name == mapping.permission.name:
                if matches_glob(perm[1], mapping.argument):
                    allowed = True
        if not allowed:
            return self.forbidden()

        self.render("permission-revoke.html", mapping=mapping)

    def post(self, name=None, mapping_id=None):
        grantable = user_grantable_permissions(self.session, self.current_user)
        mapping = PermissionMap.get(self.session, id=mapping_id)
        user_is_owner = mapping and user_is_owner_of_group(self.session, mapping.group,
            self.current_user)
        if not grantable and not user_is_owner:
            return self.forbidden()

        if not mapping:
            return self.notfound()

        allowed = user_is_owner
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
