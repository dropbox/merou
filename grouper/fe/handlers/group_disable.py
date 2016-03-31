from grouper.fe.util import GrouperHandler
from grouper.model_soup import Group
from grouper.models.audit_log import AuditLog


class GroupDisable(GrouperHandler):
    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not self.current_user.my_role(members) in ("owner", "np-owner"):
            return self.forbidden()

        group.disable()
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'disable_group',
                     'Disabled group.', on_group_id=group.id)

        if group.audit:
            # complete the audit
            group.audit.complete = True
            self.session.commit()

            AuditLog.log(self.session, self.current_user.id, 'complete_audit',
                         'Disabling group completes group audit.', on_group_id=group.id)

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
