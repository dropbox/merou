from sqlalchemy.exc import IntegrityError

from grouper.fe.forms import GroupEditForm
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.counter import Counter
from grouper.models.group import Group
from grouper.role_user import is_role_user
from grouper.user_group import user_can_manage_group


class GroupEdit(GrouperHandler):
    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not user_can_manage_group(self.session, group, self.current_user):
            return self.forbidden()

        form = GroupEditForm(obj=group)

        self.render("group-edit.html", group=group, form=form)

    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not user_can_manage_group(self.session, group, self.current_user):
            return self.forbidden()

        form = GroupEditForm(self.request.arguments, obj=group)
        if not form.validate():
            return self.render(
                "group-edit.html", group=group, form=form, alerts=self.get_form_alerts(form.errors)
            )

        if group.groupname != form.data["groupname"] and is_role_user(self.session, group=group):
            form.groupname.errors.append("You cannot change the name of service account groups")
            return self.render(
                "group-edit.html", group=group, form=form, alerts=self.get_form_alerts(form.errors)
            )

        group.groupname = form.data["groupname"]
        group.email_address = form.data["email_address"]
        group.description = form.data["description"]
        group.canjoin = form.data["canjoin"]
        group.auto_expire = form.data["auto_expire"]
        group.require_clickthru_tojoin = form.data["require_clickthru_tojoin"]
        Counter.incr(self.session, "updates")

        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            form.groupname.errors.append("{} already exists".format(form.data["groupname"]))
            return self.render(
                "group-edit.html", group=group, form=form, alerts=self.get_form_alerts(form.errors)
            )

        AuditLog.log(
            self.session, self.current_user.id, "edit_group", "Edited group.", on_group_id=group.id
        )

        return self.redirect("/groups/{}".format(group.name))
