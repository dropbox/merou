from datetime import datetime
from typing import TYPE_CHECKING

from grouper.audit import assert_can_join, UserNotAuditor
from grouper.email_util import send_email
from grouper.fe.forms import GroupJoinForm
from grouper.fe.settings import settings
from grouper.fe.util import Alert, GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group, GROUP_JOIN_CHOICES
from grouper.models.group_edge import APPROVER_ROLE_INDICES, GROUP_EDGE_ROLES
from grouper.models.user import User
from grouper.user_group import get_groups_by_user

if TYPE_CHECKING:
    from typing import Any, Optional


class GroupJoin(GrouperHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        group_id = kwargs.get("group_id")  # type: Optional[int]
        name = kwargs.get("name")  # type: Optional[str]

        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        group_md = self.graph.get_group_details(group.name)

        form = GroupJoinForm()
        form.member.choices = self._get_choices(group)
        return self.render("group-join.html", form=form, group=group, audited=group_md["audited"])

    def post(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        group_id = kwargs.get("group_id")  # type: Optional[int]
        name = kwargs.get("name")  # type: Optional[str]

        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        form = GroupJoinForm(self.request.arguments)
        form.member.choices = self._get_choices(group)
        if not form.validate():
            return self.render(
                "group-join.html", form=form, group=group, alerts=self.get_form_alerts(form.errors)
            )

        member = self._get_member(form.data["member"])

        fail_message = "This join is denied with this role at this time."
        try:
            user_can_join = assert_can_join(group, member, role=form.data["role"])
        except UserNotAuditor as e:
            user_can_join = False
            fail_message = str(e)
        if not user_can_join:
            return self.render(
                "group-join.html",
                form=form,
                group=group,
                alerts=[Alert("danger", fail_message, "Audit Policy Enforcement")],
            )

        if group.canjoin == "nobody":
            fail_message = "This group cannot be joined at this time."
            return self.render(
                "group-join.html", form=form, group=group, alerts=[Alert("danger", fail_message)]
            )

        if group.require_clickthru_tojoin:
            if not form["clickthru_agreement"]:
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

        request = group.add_member(
            requester=self.current_user,
            user_or_group=member,
            reason=form.data["reason"],
            status=GROUP_JOIN_CHOICES[group.canjoin],
            expiration=expiration,
            role=form.data["role"],
        )
        self.session.commit()

        if group.canjoin == "canask":
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

        elif group.canjoin == "canjoin":
            AuditLog.log(
                self.session,
                self.current_user.id,
                "join_group",
                "{} auto-approved to join with role: {}".format(member.name, form.data["role"]),
                on_group_id=group.id,
            )
        else:
            raise Exception("Need to update the GroupJoin.post audit logging")

        return self.redirect("/groups/{}?refresh=yes".format(group.name))

    def _get_member(self, member_choice):
        member_type, member_name = member_choice.split(": ", 1)
        resource = None

        if member_type == "User":
            resource = User
        elif member_type == "Group":
            resource = Group

        if resource is None:
            return

        return self.session.query(resource).filter_by(name=member_name, enabled=True).one()

    def _get_choices(self, group):
        choices = []

        members = group.my_members()

        if ("User", self.current_user.name) not in members:
            choices.append(("User: {}".format(self.current_user.name),) * 2)

        for _group, group_edge in get_groups_by_user(self.session, self.current_user):
            if group.name == _group.name:  # Don't add self.
                continue
            if group_edge._role not in APPROVER_ROLE_INDICES:  # manager, owner, and np-owner only.
                continue
            if ("Group", _group.name) in members:
                continue

            choices.append(("Group: {}".format(_group.name),) * 2)

        return choices
