from datetime import datetime

from sqlalchemy.exc import IntegrityError

from grouper import group as group_biz
from grouper.audit import assert_can_join, UserNotAuditor
from grouper.email_util import send_email
from grouper.fe.forms import ServiceAccountCreateForm
from grouper.fe.settings import settings
from grouper.fe.util import Alert, GrouperHandler
from grouper.model_soup import (
        APPROVER_ROLE_INDICIES,
        Group,
        GROUP_EDGE_ROLES,
        GROUP_JOIN_CHOICES,
        )
from grouper.models.audit_log import AuditLog
from grouper.models.user import User


class ServiceAccountCreate(GrouperHandler):
    def get(self):
        form = ServiceAccountCreateForm()
        return self.render(
            "service-account-create.html", form=form,
        )

    def post(self):
        form = ServiceAccountCreateForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "service-account-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        
        user = User(username=form.data["name"], role_user=True)
        group = Group(groupname=form.data["name"], description=form.data["description"],
            canjoin=form.data["canjoin"])

        try:
            user.add(self.session)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            form.name.errors.append("A user with name {} already exists".format(form.data["name"]))
            return self.render(
                "service-account-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        try:
            group.add(self.session)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            form.name.errors.append("A group with name {} already exists".format(form.data["name"]))
            return self.render(
                "service-account-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        group.add_member(self.current_user, self.current_user, "GroupCreator",
            "actioned", None, "np-owner")
        group.add_member(self.current_user, user, "Service Account",
            "actioned", None, "member")
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'create_group',
                     'Created new service account.', on_group_id=group.id)

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
