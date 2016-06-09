from datetime import datetime

from grouper.audit import assert_can_join, UserNotAuditor
from grouper.fe.forms import GroupEditMemberForm
from grouper.fe.util import Alert, GrouperHandler
from grouper.model_soup import Group, GroupEdge, User
from grouper.models.comment import OBJ_TYPES
from grouper.user import user_role


class GroupEditMember(GrouperHandler):
    def get(self, group_id=None, name=None, name2=None, member_type=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if self.current_user.name == name2:
            return self.forbidden()

        members = group.my_members()
        my_role = user_role(self.current_user, members)
        if my_role not in ("manager", "owner", "np-owner"):
            return self.forbidden()

        member = members.get((member_type.capitalize(), name2), None)
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
        if my_role in ("owner", "np-owner"):
            form.role.choices.append(["manager", "Manager"])
            form.role.choices.append(["owner", "Owner"])
            form.role.choices.append(["np-owner", "No-Permissions Owner"])

        form.role.data = edge.role
        form.expiration.data = edge.expiration.strftime("%m/%d/%Y") if edge.expiration else None

        self.render(
            "group-edit-member.html", group=group, member=member, edge=edge, form=form,
        )

    def post(self, group_id=None, name=None, name2=None, member_type=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if self.current_user.name == name2:
            return self.forbidden()

        members = group.my_members()
        my_role = user_role(self.current_user, members)
        if my_role not in ("manager", "owner", "np-owner"):
            return self.forbidden()

        member = members.get((member_type.capitalize(), name2), None)
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
        if my_role in ("owner", "np-owner"):
            form.role.choices.append(["manager", "Manager"])
            form.role.choices.append(["owner", "Owner"])
            form.role.choices.append(["np-owner", "No-Permissions Owner"])

        if not form.validate():
            return self.render(
                "group-edit-member.html", group=group, member=member, edge=edge, form=form,
                alerts=self.get_form_alerts(form.errors),
            )

        fail_message = 'This join is denied with this role at this time.'
        try:
            user_can_join = assert_can_join(group, user_or_group, role=form.data["role"])
        except UserNotAuditor as e:
            user_can_join = False
            fail_message = e
        if not user_can_join:
            return self.render(
                "group-edit-member.html", form=form, group=group, member=member, edge=edge,
                alerts=[
                    Alert('danger', fail_message, 'Audit Policy Enforcement')
                ]
            )

        expiration = None
        if form.data["expiration"]:
            expiration = datetime.strptime(form.data["expiration"], "%m/%d/%Y")

        group.edit_member(self.current_user, user_or_group, form.data["reason"],
                          role=form.data["role"], expiration=expiration)

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
