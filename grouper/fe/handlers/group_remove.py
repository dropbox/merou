from grouper.fe.forms import GroupRemoveForm
from grouper.fe.handlers.template_variables import (get_group_view_template_vars,
    get_role_user_view_template_vars)
from grouper.fe.util import Alert, GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.models.user import User
from grouper.role_user import get_role_user, is_role_user
from grouper.user import get_user_or_group
from grouper.user_group import user_can_manage_group


class GroupRemove(GrouperHandler):
    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not user_can_manage_group(self.session, group, self.current_user):
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

        if (is_role_user(self.session, group=group) and
                get_role_user(self.session, group=group).user.name == removed_member.name):
            return self.send_error(
                status_code=400,
                reason="Can't remove a service account user from the service account group."
            )

        try:
            group.revoke_member(
                self.current_user,
                removed_member,
                "Removed by owner/np-owner/manager"
            )

            AuditLog.log(self.session, self.current_user.id, 'remove_from_group',
                         '{} was removed from the group.'.format(removed_member.name),
                         on_group_id=group.id, on_user_id=removed_member.id)
        except Exception as e:
            alert = Alert("danger", str(e))
            return self._render_group_with_alert(group, alert)

        return self.redirect("/groups/{}?refresh=yes".format(group.name))

    def _render_group_with_alert(self, group, alert):
        if is_role_user(self.session, group=group):
            user = User.get(self.session, name=group.groupname)

            self.render("service.html", user=user, group=group, **get_role_user_view_template_vars(
                self.session,
                self.current_user,
                user,
                group,
                self.graph,
                alerts=[alert]
            ))

        else:
            self.render("group.html", group=group, **get_group_view_template_vars(
                self.session,
                self.current_user,
                group,
                self.graph,
                alerts=[alert]
            ))
