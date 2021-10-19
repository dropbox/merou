from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from grouper.audit import assert_controllers_are_auditors, UserNotAuditor
from grouper.fe.forms import PermissionGrantForm
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.permissions import get_permission, grant_permission
from grouper.plugin.exceptions import PluginRejectedPermissionArgument
from grouper.user_permissions import user_grantable_permissions
from grouper.util import matches_glob

if TYPE_CHECKING:
    from typing import Any


class PermissionsGrant(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        grantable = user_grantable_permissions(self.session, self.current_user)
        if not grantable:
            return self.forbidden()

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        form = PermissionGrantForm()
        form.permission.choices = [["", "(select one)"]]
        for perm in grantable:
            grantable = "{} ({})".format(perm[0].name, perm[1])
            form.permission.choices.append([perm[0].name, grantable])

        return self.render("permission-grant.html", form=form, group=group)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        grantable = user_grantable_permissions(self.session, self.current_user)
        if not grantable:
            return self.forbidden()

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        form = PermissionGrantForm(self.request.arguments)
        form.permission.choices = [["", "(select one)"]]
        for perm in grantable:
            grantable_str = "{} ({})".format(perm[0].name, perm[1])
            form.permission.choices.append([perm[0].name, grantable_str])

        if not form.validate():
            return self.render(
                "permission-grant.html",
                form=form,
                group=group,
                alerts=self.get_form_alerts(form.errors),
            )

        permission = get_permission(self.session, form.data["permission"])
        if not permission:
            return self.notfound()  # Shouldn't happen.

        argument = form.argument.data.strip()

        allowed = False
        for perm in grantable:
            if perm[0].name == permission.name:
                if matches_glob(perm[1], argument):
                    allowed = True
                    break
        if not allowed:
            msg = "You do not have grant authority over that permission/argument combination."
            if argument == "":
                msg += " (Did you mean to leave the argument field empty?)"
            form.argument.errors.append(msg)
            return self.render(
                "permission-grant.html",
                form=form,
                group=group,
                alerts=self.get_form_alerts(form.errors),
            )

        # If the permission is audited, then see if the subtree meets auditing requirements.
        if permission.audited:
            try:
                assert_controllers_are_auditors(group)
            except UserNotAuditor as e:
                form.permission.errors.append(str(e))
                return self.render(
                    "permission-grant.html",
                    form=form,
                    group=group,
                    alerts=self.get_form_alerts(form.errors),
                )

        try:
            self.plugins.check_permission_argument(permission.name, argument)
            grant_permission(self.session, group.id, permission.id, argument=argument)
        except PluginRejectedPermissionArgument as e:
            self.session.rollback()
            form.argument.errors.append(f"Rejected by plugin: {e}")
            return self.render(
                "permission-grant.html",
                form=form,
                group=group,
                alerts=self.get_form_alerts(form.errors),
            )
        except IntegrityError:
            self.session.rollback()
            form.argument.errors.append("Permission and Argument already mapped to this group.")
            return self.render(
                "permission-grant.html",
                form=form,
                group=group,
                alerts=self.get_form_alerts(form.errors),
            )

        self.session.commit()

        AuditLog.log(
            self.session,
            self.current_user.id,
            "grant_permission",
            "Granted permission with argument: {}".format(form.data["argument"]),
            on_permission_id=permission.id,
            on_group_id=group.id,
        )

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
