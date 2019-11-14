from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from grouper.audit import assert_can_join, UserNotAuditor
from grouper.fe.forms import GroupEditMemberForm
from grouper.fe.util import Alert, GrouperHandler
from grouper.group_member import InvalidRoleForMember
from grouper.models.comment import OBJ_TYPES
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.user import User
from grouper.plugin.exceptions import PluginRejectedGroupMembershipUpdate
from grouper.user import user_role

if TYPE_CHECKING:
    from typing import Any, Optional


class GroupEditMember(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        group_id: Optional[int] = kwargs.get("group_id")
        group_name: Optional[str] = kwargs.get("name")
        user: str = kwargs["name2"]
        member_type: str = kwargs["member_type"]

        group = Group.get(self.session, group_id, group_name)
        if not group:
            return self.notfound()

        if self.current_user.name == user:
            return self.forbidden()

        members = group.my_members()
        my_role = user_role(self.current_user, members)
        if my_role not in ("manager", "owner", "np-owner"):
            return self.forbidden()

        member = members.get((member_type.capitalize(), user), None)
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

        form = GroupEditMemberForm(self.request.arguments)
        form.role.choices = [["member", "Member"]]
        if my_role in ("owner", "np-owner") and member_type != "group":
            form.role.choices.append(["manager", "Manager"])
            form.role.choices.append(["owner", "Owner"])
            form.role.choices.append(["np-owner", "No-Permissions Owner"])
        else:
            form.role.render_kw = {"readonly": "readonly"}

        form.role.data = edge.role
        form.expiration.data = edge.expiration.strftime("%m/%d/%Y") if edge.expiration else None

        self.render("group-edit-member.html", group=group, member=member, edge=edge, form=form)

    def post(self, *args: Any, **kwargs: Any) -> None:
        group_id: Optional[int] = kwargs.get("group_id")
        group_name: Optional[str] = kwargs.get("name")
        user: str = kwargs["name2"]
        member_type: str = kwargs["member_type"]

        group = Group.get(self.session, group_id, group_name)
        if not group:
            return self.notfound()

        if self.current_user.name == user:
            return self.forbidden()

        members = group.my_members()
        my_role = user_role(self.current_user, members)
        if my_role not in ("manager", "owner", "np-owner"):
            return self.forbidden()

        member = members.get((member_type.capitalize(), user), None)
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

        form = GroupEditMemberForm(self.request.arguments)
        form.role.choices = [["member", "Member"]]
        if my_role in ("owner", "np-owner") and member_type != "group":
            form.role.choices.append(["manager", "Manager"])
            form.role.choices.append(["owner", "Owner"])
            form.role.choices.append(["np-owner", "No-Permissions Owner"])
        else:
            form.role.render_kw = {"readonly": "readonly"}

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
