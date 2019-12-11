from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from grouper.audit import assert_can_join, UserNotAuditor
from grouper.email_util import send_email
from grouper.entities.group_edge import APPROVER_ROLE_INDICES, GROUP_EDGE_ROLES
from grouper.fe.alerts import Alert
from grouper.fe.forms import GroupJoinForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.group_member import InvalidRoleForMember
from grouper.group_requests import count_requests_by_group
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group, GROUP_JOIN_CHOICES
from grouper.models.user import User
from grouper.user_group import get_groups_by_user

if TYPE_CHECKING:
    from typing import Any, Mapping, List, Optional, Set, Tuple, Union


class GroupJoin(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        group = Group.get(self.session, name=name)
        if not group or not group.enabled:
            return self.notfound()

        group_md = self.graph.get_group_details(group.name)

        members = group.my_members()
        member_groups = {g for t, g in members if t == "Group"}
        user_is_member = self._is_user_a_member(group, members)

        form = GroupJoinForm()
        form.member.choices = self._get_choices(group, member_groups, user_is_member)
        return self.render(
            "group-join.html",
            form=form,
            group=group,
            audited=group_md["audited"],
            user_is_member=user_is_member,
        )

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        group = Group.get(self.session, name=name)
        if not group or not group.enabled:
            return self.notfound()

        members = group.my_members()
        member_groups = {g for t, g in members if t == "Group"}
        user_is_member = self._is_user_a_member(group, members)

        form = GroupJoinForm(self.request.arguments)
        form.member.choices = self._get_choices(group, member_groups, user_is_member)
        if not form.validate():
            return self.render(
                "group-join.html", form=form, group=group, alerts=self.get_form_alerts(form.errors)
            )

        member = self._get_member(form.data["member"])
        if not member:
            return self.render(
                "group-join.html",
                form=form,
                group=group,
                alerts=[Alert("danger", "Unknown user or group: {}".format(form.data["member"]))],
            )

        try:
            assert_can_join(group, member, role=form.data["role"])
        except UserNotAuditor as e:
            return self.render(
                "group-join.html",
                form=form,
                group=group,
                alerts=[Alert("danger", str(e), "Audit Policy Enforcement")],
            )

        if group.canjoin == "nobody":
            fail_message = "This group cannot be joined at this time."
            return self.render(
                "group-join.html", form=form, group=group, alerts=[Alert("danger", fail_message)]
            )

        if group.require_clickthru_tojoin:
            if not form.data["clickthru_agreement"]:
                return self.render(
                    "group-join.html",
                    form=form,
                    group=group,
                    alerts=[
                        Alert(
                            "danger",
                            "please accept review of the group's description",
                            "Clickthru Enforcement",
                        )
                    ],
                )

        # We only use the default expiration time if no expiration time was given
        # This does mean that if a user wishes to join a group with no expiration
        # (even with an owner's permission) that has an auto expiration, they must
        # first be accepted to the group and then have the owner edit the user to
        # have no expiration.

        expiration = None
        if form.data["expiration"]:
            expiration = datetime.strptime(form.data["expiration"], "%m/%d/%Y")
        elif group.auto_expire:
            expiration = datetime.utcnow() + group.auto_expire

        # If the requested role is member, set the status based on the group's canjoin setting,
        # which automatically actions the request if the group can be joined by anyone and
        # otherwise sets it pending.
        #
        # However, we don't want to let people autojoin as owner or np-owner even to otherwise open
        # groups, so if the role is not member, force the status to pending.
        if form.data["role"] == "member":
            status = GROUP_JOIN_CHOICES[group.canjoin]
        else:
            status = "pending"

        try:
            request = group.add_member(
                requester=self.current_user,
                user_or_group=member,
                reason=form.data["reason"],
                status=status,
                expiration=expiration,
                role=form.data["role"],
            )
        except InvalidRoleForMember as e:
            return self.render(
                "group-join.html",
                form=form,
                group=group,
                alerts=[Alert("danger", str(e), "Invalid Role")],
            )
        self.session.commit()

        if status == "pending":
            AuditLog.log(
                self.session,
                self.current_user.id,
                "join_group",
                "{} requested to join with role: {}".format(member.name, form.data["role"]),
                on_group_id=group.id,
            )

            mail_to = [
                user.name
                for user in group.my_users()
                if GROUP_EDGE_ROLES[user.role] in ("manager", "owner", "np-owner")
            ]

            email_context = {
                "requester": member.name,
                "requested_by": self.current_user.name,
                "request_id": request.id,
                "group_name": group.name,
                "reason": form.data["reason"],
                "expiration": expiration,
                "role": form.data["role"],
                "references_header": request.reference_id,
            }

            subj = self.render_template(
                "email/pending_request_subj.tmpl", group=group.name, user=self.current_user.name
            )
            send_email(self.session, mail_to, subj, "pending_request", settings(), email_context)

        elif status == "actioned":
            AuditLog.log(
                self.session,
                self.current_user.id,
                "join_group",
                "{} auto-approved to join with role: {}".format(member.name, form.data["role"]),
                on_group_id=group.id,
            )
        else:
            raise Exception(f"Unknown join status {status}")

        return self.redirect("/groups/{}?refresh=yes".format(group.name))

    def _get_member(self, member_choice: str) -> Optional[Union[User, Group]]:
        member_type, member_name = member_choice.split(": ", 1)
        resource = None

        if member_type == "User":
            resource = User
        elif member_type == "Group":
            resource = Group

        if resource is None:
            return None

        return self.session.query(resource).filter_by(name=member_name, enabled=True).one()

    def _get_choices(
        self, group: Group, member_groups: Set[str], user_is_member: bool
    ) -> List[Tuple[str, str]]:
        choices = []

        if not user_is_member:
            choice = "User: {}".format(self.current_user.name)
            choices.append((choice, choice))

        for _group, group_edge in get_groups_by_user(self.session, self.current_user):
            if group.name == _group.name:  # Don't add self.
                continue
            if group_edge._role not in APPROVER_ROLE_INDICES:  # manager, owner, and np-owner only.
                continue
            if _group.name in member_groups:
                continue

            choice = "Group: {}".format(_group.name)
            choices.append((choice, choice))

        # If there are some choices but the user is already a member or has a pending request, add
        # a blank option as the first choice to avoid the user requesting membership on behalf of a
        # group by mistake.
        if choices and user_is_member:
            choices.insert(0, ("", ""))

        return choices

    def _is_user_a_member(self, group: Group, members: Mapping[Tuple[str, str], Any]) -> bool:
        """Returns whether the current user is a member or has a pending membership request."""
        if ("User", self.current_user.name) in members:
            return True
        if count_requests_by_group(self.session, group, "pending", self.current_user) > 0:
            return True
        return False
