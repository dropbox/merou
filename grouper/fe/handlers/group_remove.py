from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.alerts import Alert
from grouper.fe.forms import GroupRemoveForm
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.plugin.exceptions import PluginRejectedGroupMembershipUpdate
from grouper.role_user import get_role_user, is_role_user
from grouper.user import get_user_or_group
from grouper.user_group import user_can_manage_group

if TYPE_CHECKING:
    from typing import Any


class GroupRemove(GrouperHandler):
    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        group = Group.get(self.session, name=name)
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
            return self.send_error(
                status_code=400,
                reason="Invalid remove request: {} is not a member of {}.".format(
                    member_name, group.name
                ),
            )

        removed_member = get_user_or_group(self.session, member_name, user_or_group=member_type)

        if self.current_user == removed_member:
            return self.send_error(
                status_code=400, reason="Can't remove yourself. Leave group instead."
            )

        role_user = is_role_user(self.session, group=group)

        if role_user and get_role_user(self.session, group=group).user.name == removed_member.name:
            return self.send_error(
                status_code=400,
                reason="Can't remove a service account user from the service account group.",
            )

        try:
            group.revoke_member(
                self.current_user, removed_member, "Removed by owner/np-owner/manager"
            )

            AuditLog.log(
                self.session,
                self.current_user.id,
                "remove_from_group",
                "{} was removed from the group.".format(removed_member.name),
                on_group_id=group.id,
                on_user_id=removed_member.id,
            )
        except PluginRejectedGroupMembershipUpdate as e:
            alert = Alert("danger", str(e))

            if role_user:
                return self.redirect("/service/{}".format(group.name), alerts=[alert])
            else:
                return self.redirect("/groups/{}".format(group.name), alerts=[alert])

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
