from __future__ import annotations

import operator
from datetime import datetime
from typing import TYPE_CHECKING

from grouper.audit import assert_can_join, UserNotAuditor
from grouper.email_util import send_email
from grouper.fe.alerts import Alert
from grouper.fe.forms import GroupAddForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.group import get_all_groups
from grouper.group_member import InvalidRoleForMember
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.role_user import get_role_user, is_role_user
from grouper.user import get_all_enabled_users, get_user_or_group, user_role
from grouper.user_group import user_can_manage_group

if TYPE_CHECKING:
    from typing import Any


class GroupAdd(GrouperHandler):
    def get_form(self, role: str) -> GroupAddForm:
        """Helper to create a GroupAddForm populated with all users and groups as options.

        Note that the first choice is blank so the first user alphabetically
        isn't always selected.
        """

        form = GroupAddForm(self.request.arguments)

        form.role.choices = [["member", "Member"]]
        if role in ("owner", "np-owner"):
            form.role.choices.append(["manager", "Manager"])
            form.role.choices.append(["owner", "Owner"])
            form.role.choices.append(["np-owner", "No-Permissions Owner"])

        group_choices = [
            (group.groupname, "Group: " + group.groupname)  # (value, label)
            for group in get_all_groups(self.session)
        ]
        user_choices = [
            (user.username, "User: " + user.username)  # (value, label)
            for user in get_all_enabled_users(self.session, include_service_accounts=False)
        ]

        form.member.choices = [("", "")] + sorted(
            group_choices + user_choices, key=operator.itemgetter(1)
        )
        return form

    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        if not user_can_manage_group(self.session, group, self.current_user):
            return self.forbidden()

        members = group.my_members()
        my_role = user_role(self.current_user, members)
        return self.render("group-add.html", form=self.get_form(role=my_role), group=group)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        if not user_can_manage_group(self.session, group, self.current_user):
            return self.forbidden()

        members = group.my_members()
        my_role = user_role(self.current_user, members)
        form = self.get_form(role=my_role)
        if not form.validate():
            return self.render(
                "group-add.html", form=form, group=group, alerts=self.get_form_alerts(form.errors)
            )

        member = get_user_or_group(self.session, form.data["member"])
        if member.type == "User" and is_role_user(self.session, member):
            # For service accounts, we want to always add the group to other groups, not the user
            member = get_role_user(self.session, user=member).group
        if not member:
            form.member.errors.append("User or group not found.")
        elif (member.type, member.name) in group.my_members():
            form.member.errors.append("User or group is already a member of this group.")
        elif group.name == member.name:
            form.member.errors.append("By definition, this group is a member of itself already.")

        # Ensure this doesn't violate auditing constraints
        try:
            assert_can_join(group, member, role=form.data["role"])
        except UserNotAuditor as e:
            form.member.errors.append(str(e))

        if form.member.errors:
            return self.render(
                "group-add.html", form=form, group=group, alerts=self.get_form_alerts(form.errors)
            )

        expiration = None
        if form.data["expiration"]:
            expiration = datetime.strptime(form.data["expiration"], "%m/%d/%Y")

        try:
            group.add_member(
                requester=self.current_user,
                user_or_group=member,
                reason=form.data["reason"],
                status="actioned",
                expiration=expiration,
                role=form.data["role"],
            )
        except InvalidRoleForMember as e:
            return self.render(
                "group-add.html", form=form, group=group, alerts=[Alert("danger", str(e))]
            )

        self.session.commit()

        on_user_id = member.id if member.type == "User" else None
        AuditLog.log(
            self.session,
            self.current_user.id,
            "join_group",
            "{} added to group with role: {}".format(member.name, form.data["role"]),
            on_group_id=group.id,
            on_user_id=on_user_id,
        )

        if member.type == "User":
            send_email(
                self.session,
                [member.name],
                "Added to group: {}".format(group.name),
                "request_actioned",
                settings(),
                {
                    "group_name": group.name,
                    "actioned_by": self.current_user.name,
                    "reason": form.data["reason"],
                    "expiration": expiration,
                    "role": form.data["role"],
                },
            )

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
