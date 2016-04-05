from sqlalchemy.exc import IntegrityError
from grouper.fe.forms import GroupEditForm
from grouper.fe.util import GrouperHandler
from grouper.model_soup import Group
from grouper.models.counter import Counter
from grouper.models.audit_log import AuditLog


class GroupEdit(GrouperHandler):
    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not self.current_user.can_manage(group):
            return self.forbidden()

        form = GroupEditForm(obj=group)

        self.render("group-edit.html", group=group, form=form)

    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not self.current_user.can_manage(group):
            return self.forbidden()

        form = GroupEditForm(self.request.arguments, obj=group)
        if not form.validate():
            return self.render(
                "group-edit.html", group=group, form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        group.groupname = form.data["groupname"]
        group.description = form.data["description"]
        group.canjoin = form.data["canjoin"]
        Counter.incr(self.session, "updates")

        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            form.groupname.errors.append(
                "{} already exists".format(form.data["groupname"])
            )
            return self.render(
                "group-edit.html", group=group, form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        AuditLog.log(self.session, self.current_user.id, 'edit_group',
                     'Edited group.', on_group_id=group.id)

        return self.redirect("/groups/{}".format(group.name))
