from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.forms import GroupEditForm
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.counter import Counter
from grouper.models.group import Group
from grouper.role_user import is_role_user
from grouper.user_group import user_can_manage_group

if TYPE_CHECKING:
    from typing import Any


class GroupEdit(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        if not user_can_manage_group(self.session, group, self.current_user):
            return self.forbidden()

        form = GroupEditForm(obj=group)

        self.render("group-edit.html", group=group, form=form)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        if not user_can_manage_group(self.session, group, self.current_user):
            return self.forbidden()

        form = GroupEditForm(self.request.arguments, obj=group)
        if not form.validate():
            return self.render(
                "group-edit.html", group=group, form=form, alerts=self.get_form_alerts(form.errors)
            )

        new_name = form.data["groupname"]
        renamed = group.groupname != new_name

        if renamed and is_role_user(self.session, group=group):
            form.groupname.errors.append("You cannot change the name of service account groups")
            return self.render(
                "group-edit.html", group=group, form=form, alerts=self.get_form_alerts(form.errors)
            )

        if renamed and Group.get(self.session, name=new_name):
            message = f"A group named '{new_name}' already exists (possibly disabled)"
            form.groupname.errors.append(message)
            return self.render(
                "group-edit.html", group=group, form=form, alerts=self.get_form_alerts(form.errors)
            )

        group.groupname = new_name
        group.email_address = form.data["email_address"]
        group.description = form.data["description"]
        group.canjoin = form.data["canjoin"]
        group.auto_expire = form.data["auto_expire"]
        group.require_clickthru_tojoin = form.data["require_clickthru_tojoin"]
        Counter.incr(self.session, "updates")
        self.session.commit()

        AuditLog.log(
            self.session, self.current_user.id, "edit_group", "Edited group.", on_group_id=group.id
        )

        url = f"/groups/{group.name}"
        if renamed:
            url += "?refresh=yes"
        self.redirect(url)
