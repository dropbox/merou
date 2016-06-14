from grouper.fe.util import GrouperHandler
from grouper.model_soup import Group
from grouper.models.audit_log import AuditLog
from grouper.user import user_role


class GroupEnable(GrouperHandler):
    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not user_role(self.current_user, members) in ("owner", "np-owner"):
            return self.forbidden()

        group.enable()
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'enable_group',
                     'Enabled group.', on_group_id=group.id)

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
