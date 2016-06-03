from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.counter import Counter
from grouper.models.tag_permission_map import TagPermissionMap
from grouper.constants import TAG_EDIT


class PermissionsRevokeTag(GrouperHandler):
    def get(self, name=None, mapping_id=None):

        mapping = TagPermissionMap.get(self.session, id=mapping_id)
        if not mapping:
            return self.notfound()

        if not self.current_user.has_permission(TAG_EDIT, mapping.tag.name):
            return self.forbidden()

        self.render("permission-revoke-tag.html", mapping=mapping)

    def post(self, name=None, mapping_id=None):
        mapping = TagPermissionMap.get(self.session, id=mapping_id)
        if not mapping:
            return self.notfound()

        if not self.current_user.has_permission(TAG_EDIT, mapping.tag.name):
            return self.forbidden()

        permission = mapping.permission
        tag = mapping.tag

        mapping.delete(self.session)
        Counter.incr(self.session, "updates")
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'revoke_tag_permission',
                     'Revoked permission with argument: {}'.format(mapping.argument),
                     on_tag_id=tag.id, on_permission_id=permission.id)

        return self.redirect('/tags/{}?refresh=yes'.format(tag.name))
