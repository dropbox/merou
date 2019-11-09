from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from grouper.audit import assert_can_join, UserNotAuditor
from grouper.fe.alerts import Alert
from grouper.fe.forms import GroupEditMemberForm
from grouper.fe.util import GrouperHandler
from grouper.group_member import InvalidRoleForMember
from grouper.models.comment import OBJ_TYPES
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.user import User
from grouper.plugin.exceptions import PluginRejectedGroupMembershipUpdate
from grouper.user import user_role

if TYPE_CHECKING:
    from typing import Any


class GroupEditMember(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")
        member_name = self.get_path_argument("member_name")
        member_type = self.get_path_argument("member_type")

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        members = group.my_members()
        my_role = user_role(self.current_user, members)
        if my_role not in ("manager", "owner", "np-owner"):
            return self.forbidden()

        member = members.get((member_type.capitalize(), member_name), None)
        if not member:
            return self.notfound()

        edge = GroupEdge.get(
            self.session,
            group_id=group.id,
            member_type=OBJ_TYPES[member.type],
            member_pk=member.id,
        )
        if not edge:
            return self.notfound()

        form = self._get_form(member_name, my_role, member_type)
        form.role.data = edge.role
        form.expiration.data = edge.expiration.strftime("%m/%d/%Y") if edge.expiration else None

        self.render("group-edit-member.html", group=group, member=member, edge=edge, form=form)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")
        member_name = self.get_path_argument("member_name")
        member_type = self.get_path_argument("member_type")

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        members = group.my_members()
        my_role = user_role(self.current_user, members)
        if my_role not in ("manager", "owner", "np-owner"):
            return self.forbidden()

        member = members.get((member_type.capitalize(), member_name), None)
        if not member:
            return self.notfound()

        if member.type == "Group":
            user_or_group = Group.get(self.session, member.id)
        else:
            user_or_group = User.get(self.session, member.id)
        if not user_or_group:
            return self.notfound()

        edge = GroupEdge.get(
            self.session,
            group_id=group.id,
            member_type=OBJ_TYPES[member.type],
            member_pk=member.id,
        )
        if not edge:
            return self.notfound()

        form = self._get_form(member_name, my_role, member_type)
        if not form.validate():
            return self.render(
                "group-edit-member.html",
                group=group,
                member=member,
                edge=edge,
                form=form,
                alerts=self.get_form_alerts(form.errors),
            )

        try:
            assert_can_join(group, user_or_group, role=form.data["role"])
        except UserNotAuditor as e:
            return self.render(
                "group-edit-member.html",
                form=form,
                group=group,
                member=member,
                edge=edge,
                alerts=[Alert("danger", str(e), "Audit Policy Enforcement")],
            )

        expiration = None
        if form.data["expiration"]:
            expiration = datetime.strptime(form.data["expiration"], "%m/%d/%Y")

        try:
            group.edit_member(
                self.current_user,
                user_or_group,
                form.data["reason"],
                role=form.data["role"],
                expiration=expiration,
            )
        except (InvalidRoleForMember, PluginRejectedGroupMembershipUpdate) as e:
            return self.render(
                "group-edit-member.html",
                form=form,
                group=group,
                member=member,
                edge=edge,
                alerts=[Alert("danger", str(e))],
            )

        return self.redirect("/groups/{}?refresh=yes".format(group.name))

    def _get_form(self, user: str, my_role: str, member_type: str) -> GroupEditMemberForm:
        """Get the form with possible role options filled in.

        Groups cannot have their role changed at all.

        Any owner or manager role can change the role of another user (this is a little weird for
        manager, but we let them approve membership for any role, and manager is going to go away
        in the future, so allow this).

        Owners, np-owners, and managers can edit their own membership, but not upgrade it.
        Therefore, we only allow (owner -> ANY, np-owner -> member, manager -> member).  Don't
        attempt here to figure out if they're downgrading the last owner; we'll catch that later.
        """
        form = GroupEditMemberForm(self.request.arguments)
        form.role.choices = [["member", "Member"]]
        if member_type == "group":
            form.role.render_kw = {"readonly": "readonly"}
        elif user != self.current_user.username or my_role == "owner":
            form.role.choices.append(["manager", "Manager"])
            form.role.choices.append(["np-owner", "No-Permissions Owner"])
            form.role.choices.append(["owner", "Owner"])
        elif my_role == "manager":
            form.role.choices.append(["manager", "Manager"])
        elif my_role == "np-owner":
            form.role.choices.append(["np-owner", "No-Permissions Owner"])

        return form
