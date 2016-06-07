from datetime import datetime

from grouper import group as group_biz
from grouper.audit import assert_can_join, UserNotAuditor
from grouper.email_util import send_email
from grouper.fe.forms import GroupJoinForm
from grouper.fe.settings import settings
from grouper.fe.util import Alert, GrouperHandler
from grouper.model_soup import (
        APPROVER_ROLE_INDICIES,
        Group,
        GROUP_EDGE_ROLES,
        GROUP_JOIN_CHOICES,
        User,
        )
from grouper.models.audit_log import AuditLog


class GroupJoin(GrouperHandler):
    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        group_md = self.graph.get_group_details(group.name)

        form = GroupJoinForm()
        form.member.choices = self._get_choices(group)
        return self.render(
            "group-join.html", form=form, group=group, audited=group_md["audited"],
        )

    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        form = GroupJoinForm(self.request.arguments)
        form.member.choices = self._get_choices(group)
        if not form.validate():
            return self.render(
                "group-join.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors)
            )

        member = self._get_member(form.data["member"])

        fail_message = 'This join is denied with this role at this time.'
        try:
            user_can_join = assert_can_join(group, member, role=form.data["role"])
        except UserNotAuditor as e:
            user_can_join = False
            fail_message = e
        if not user_can_join:
            return self.render(
                "group-join.html", form=form, group=group,
                alerts=[
                    Alert('danger', fail_message, 'Audit Policy Enforcement')
                ]
            )

        if group.canjoin == "nobody":
            fail_message = 'This group cannot be joined at this time.'
            return self.render(
                "group-join.html", form=form, group=group,
                alerts=[
                    Alert('danger', fail_message)
                ]
            )

        expiration = None
        if form.data["expiration"]:
            expiration = datetime.strptime(form.data["expiration"], "%m/%d/%Y")

        group.add_member(
            requester=self.current_user,
            user_or_group=member,
            reason=form.data["reason"],
            status=GROUP_JOIN_CHOICES[group.canjoin],
            expiration=expiration,
            role=form.data["role"]
        )
        self.session.commit()

        if group.canjoin == 'canask':
            AuditLog.log(self.session, self.current_user.id, 'join_group',
                         '{} requested to join with role: {}'.format(
                             member.name, form.data["role"]),
                         on_group_id=group.id)

            mail_to = [
                user.name
                for user in group.my_users()
                if GROUP_EDGE_ROLES[user.role] in ('manager', 'owner', 'np-owner')
            ]

            email_context = {
                    "requester": member.name,
                    "requested_by": self.current_user.name,
                    "group_name": group.name,
                    "reason": form.data["reason"],
                    "expiration": expiration,
                    "role": form.data["role"],
                    }
            send_email(self.session, mail_to, 'Request to join: {}'.format(group.name),
                    'pending_request', settings, email_context)

        elif group.canjoin == 'canjoin':
            AuditLog.log(self.session, self.current_user.id, 'join_group',
                         '{} auto-approved to join with role: {}'.format(
                             member.name, form.data["role"]),
                         on_group_id=group.id)
        else:
            raise Exception('Need to update the GroupJoin.post audit logging')

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

        return self.session.query(resource).filter_by(
            name=member_name, enabled=True
        ).one()

    def _get_choices(self, group):
        choices = []

        members = group.my_members()

        if ("User", self.current_user.name) not in members:
            choices.append(
                ("User: {}".format(self.current_user.name), ) * 2
            )

        for _group, group_edge in group_biz.get_groups_by_user(self.session, self.current_user):
            if group.name == _group.name:  # Don't add self.
                continue
            if group_edge._role not in APPROVER_ROLE_INDICIES:  # manager, owner, and np-owner only.
                continue
            if ("Group", _group.name) in members:
                continue

            choices.append(
                ("Group: {}".format(_group.name), ) * 2
            )

        return choices
