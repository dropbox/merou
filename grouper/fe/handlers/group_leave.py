from grouper.fe.util import GrouperHandler
from grouper.model_soup import Group
from grouper.models.audit_log import AuditLog


class GroupLeave(GrouperHandler):
    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not self.current_user.my_role(members):
            return self.forbidden()

        return self.render(
            "group-leave.html", group=group
        )

    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not self.current_user.my_role(members):
            return self.forbidden()

        group.revoke_member(self.current_user, self.current_user, "User self-revoked.")

        AuditLog.log(self.session, self.current_user.id, 'leave_group',
                     '{} left the group.'.format(self.current_user.name),
                     on_group_id=group.id)

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
