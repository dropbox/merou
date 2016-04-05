from grouper.fe.forms import GroupRemoveForm
from grouper.fe.util import GrouperHandler
from grouper.model_soup import Group
from grouper.user import get_user_or_group
from grouper.models.audit_log import AuditLog


class GroupRemove(GrouperHandler):
    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not self.current_user.can_manage(group):
            return self.forbidden()

        form = GroupRemoveForm(self.request.arguments)
        if not form.validate():
            return self.send_error(status_code=400)

        member_type, member_name = form.data["member_type"], form.data["member"]

        members = group.my_members()
        if not members.get((member_type.capitalize(), member_name), None):
            return self.notfound()

        removed_member = get_user_or_group(self.session, member_name, user_or_group=member_type)

        if self.current_user == removed_member:
            return self.send_error(
                status_code=400,
                reason="Can't remove yourself. Leave group instead."
            )

        group.revoke_member(self.current_user, removed_member, "Removed by owner/np-owner/manager")
        AuditLog.log(self.session, self.current_user.id, 'remove_from_group',
                     '{} was removed from the group.'.format(removed_member.name),
                     on_group_id=group.id, on_user_id=removed_member.id)
        return self.redirect("/groups/{}?refresh=yes".format(group.name))
