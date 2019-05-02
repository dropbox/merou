from sqlalchemy.exc import IntegrityError

from grouper.fe.forms import PermissionCreateForm
from grouper.fe.util import GrouperHandler, test_reserved_names
from grouper.models.audit_log import AuditLog
from grouper.permissions import create_permission
from grouper.user_permissions import user_creatable_permissions
from grouper.util import matches_glob


class PermissionsCreate(GrouperHandler):
    def get(self):
        can_create = user_creatable_permissions(self.session, self.current_user)
        if not can_create:
            return self.forbidden()

        return self.render(
            "permission-create.html", form=PermissionCreateForm(), can_create=sorted(can_create)
        )

    def post(self):
        can_create = user_creatable_permissions(self.session, self.current_user)
        if not can_create:
            return self.forbidden()

        form = PermissionCreateForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "permission-create.html", form=form, alerts=self.get_form_alerts(form.errors)
            )

        # A user is allowed to create a permission if the name matches any of the globs that they
        # are given access to via PERMISSION_CREATE, as long as the permission does not match a
        # reserved name. (Unless specifically granted.)
        allowed = False
        for creatable in can_create:
            if matches_glob(creatable, form.data["name"]):
                allowed = True

        for failure_message in test_reserved_names(form.data["name"]):
            form.name.errors.append(failure_message)

        if not allowed:
            form.name.errors.append("Permission name does not match any of your allowed patterns.")

        if form.name.errors:
            return self.render(
                "permission-create.html", form=form, alerts=self.get_form_alerts(form.errors)
            )

        try:
            permission = create_permission(
                self.session, form.data["name"], form.data["description"]
            )
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            form.name.errors.append("Name already in use. Permissions must be unique.")
            return self.render(
                "permission-create.html",
                form=form,
                can_create=sorted(can_create),
                alerts=self.get_form_alerts(form.errors),
            )

        self.session.commit()

        AuditLog.log(
            self.session,
            self.current_user.id,
            "create_permission",
            "Created permission.",
            on_permission_id=permission.id,
        )

        # No explicit refresh because handler queries SQL.
        return self.redirect("/permissions/{}".format(permission.name))
