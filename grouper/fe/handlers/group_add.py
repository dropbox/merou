import operator
from datetime import datetime
from grouper.audit import assert_can_join, UserNotAuditor
from grouper.email_util import send_email
from grouper.fe.forms import GroupAddForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.group import get_all_groups
from grouper.model_soup import Group
from grouper.user import get_all_users, get_user_or_group
from grouper.models.audit_log import AuditLog


class GroupAdd(GrouperHandler):
    def get_form(self, role=None):
        """Helper to create a GroupAddForm populated with all users and groups as options.

        Note that the first choice is blank so the first user alphabetically
        isn't always selected.

        Returns:
            GroupAddForm object.
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
            for user in get_all_users(self.session)
        ]

        form.member.choices = [("", "")] + sorted(
            group_choices + user_choices,
            key=operator.itemgetter(1)
        )
        return form

    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not self.current_user.can_manage(group):
            return self.forbidden()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        return self.render(
            "group-add.html", form=self.get_form(role=my_role), group=group
        )

    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not self.current_user.can_manage(group):
            return self.forbidden()

        members = group.my_members()
        my_role = self.current_user.my_role(members)
        form = self.get_form(role=my_role)
        if not form.validate():
            return self.render(
                "group-add.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors)
            )

        member = get_user_or_group(self.session, form.data["member"])
        if not member:
            form.member.errors.append("User or group not found.")
        elif (member.type, member.name) in group.my_members():
            form.member.errors.append("User or group is already a member of this group.")
        elif group.name == member.name:
            form.member.errors.append("By definition, this group is a member of itself already.")

        # Ensure this doesn't violate auditing constraints
        fail_message = 'This join is denied with this role at this time.'
        try:
            user_can_join = assert_can_join(group, member, role=form.data["role"])
        except UserNotAuditor as e:
            user_can_join = False
            fail_message = e
        if not user_can_join:
            form.member.errors.append(fail_message)

        if form.member.errors:
            return self.render(
                "group-add.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors)
            )

        expiration = None
        if form.data["expiration"]:
            expiration = datetime.strptime(form.data["expiration"], "%m/%d/%Y")

        group.add_member(
            requester=self.current_user,
            user_or_group=member,
            reason=form.data["reason"],
            status='actioned',
            expiration=expiration,
            role=form.data["role"]
        )
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'join_group',
                     '{} added to group with role: {}'.format(
                         member.name, form.data["role"]),
                     on_group_id=group.id)

        if member.type == "User":
            send_email(
                self.session,
                [member.name],
                'Added to group: {}'.format(group.name),
                'request_actioned',
                settings,
                {
                    'group': group.name,
                    'actioned_by': self.current_user.name,
                    'reason': form.data['reason'],
                    'expiration': expiration,
                    'role': form.data['role'],
                }
            )

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
