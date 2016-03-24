from sqlalchemy.exc import IntegrityError
from grouper.audit import assert_controllers_are_auditors, UserNotAuditor
from grouper.fe.forms import PermissionGrantForm
from grouper.fe.util import GrouperHandler
from grouper.models import AuditLog, Group, Permission
from grouper.util import matches_glob


class PermissionsGrant(GrouperHandler):
    def get(self, name=None):
        grantable = self.current_user.my_grantable_permissions()
        if not grantable:
            return self.forbidden()

        group = Group.get(self.session, None, name)
        if not group:
            return self.notfound()

        form = PermissionGrantForm()
        form.permission.choices = [["", "(select one)"]]
        for perm in grantable:
            grantable = "{} ({})".format(perm[0].name, perm[1])
            form.permission.choices.append([perm[0].name, grantable])

        return self.render(
            "permission-grant.html", form=form, group=group,
        )

    def post(self, name=None):
        grantable = self.current_user.my_grantable_permissions()
        if not grantable:
            return self.forbidden()

        group = Group.get(self.session, None, name)
        if not group:
            return self.notfound()

        form = PermissionGrantForm(self.request.arguments)
        form.permission.choices = [["", "(select one)"]]
        for perm in grantable:
            grantable_str = "{} ({})".format(perm[0].name, perm[1])
            form.permission.choices.append([perm[0].name, grantable_str])

        if not form.validate():
            return self.render(
                "permission-grant.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors)
            )

        permission = Permission.get(self.session, form.data["permission"])
        if not permission:
            return self.notfound()  # Shouldn't happen.

        allowed = False
        for perm in grantable:
            if perm[0].name == permission.name:
                if matches_glob(perm[1], form.data["argument"]):
                    allowed = True
        if not allowed:
            form.argument.errors.append(
                "You do not have grant authority over that permission/argument combination."
            )
            return self.render(
                "permission-grant.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors),
            )

        # If the permission is audited, then see if the subtree meets auditing requirements.
        if permission.audited:
            fail_message = ("Permission is audited and this group (or a subgroup) contains " +
                            "owners, np-owners, or managers who have not received audit training.")
            try:
                permission_ok = assert_controllers_are_auditors(group)
            except UserNotAuditor as e:
                permission_ok = False
                fail_message = e
            if not permission_ok:
                form.permission.errors.append(fail_message)
                return self.render(
                    "permission-grant.html", form=form, group=group,
                    alerts=self.get_form_alerts(form.errors),
                )

        try:
            group.grant_permission(permission, argument=form.data["argument"])
        except IntegrityError:
            form.argument.errors.append(
                "Permission and Argument already mapped to this group."
            )
            return self.render(
                "permission-grant.html", form=form, group=group,
                alerts=self.get_form_alerts(form.errors),
            )

        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'grant_permission',
                     'Granted permission with argument: {}'.format(form.data["argument"]),
                     on_permission_id=permission.id, on_group_id=group.id)

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
