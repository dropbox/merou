from sqlalchemy.exc import IntegrityError

from grouper.constants import USER_ADMIN
from grouper.fe.forms import ServiceAccountPermissionGrantForm
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.models.permission import Permission
from grouper.models.service_account import ServiceAccount
from grouper.permissions import grant_permission_to_service_account
from grouper.service_account import can_manage_service_account
from grouper.user_permissions import user_has_permission
from grouper.util import matches_glob


class ServiceAccountPermissionGrant(GrouperHandler):
    @staticmethod
    def check_access(session, actor, target):
        if user_has_permission(session, actor, USER_ADMIN):
            return True
        return can_manage_service_account(session, target, actor)

    def get_form(self, grantable):
        """Helper to create a ServiceAccountPermissionGrantForm.

        Populate it with all the permissions held by the group.  Note that the first choice is
        blank so the first user alphabetically isn't always selected.

        Returns:
            ServiceAccountPermissionGrantForm object.
        """
        form = ServiceAccountPermissionGrantForm(self.request.arguments)
        form.permission.choices = [["", "(select one)"]]
        for perm in grantable:
            entry = "{} ({})".format(perm[1], perm[3])
            form.permission.choices.append([perm[1], entry])
        return form

    def get(self, group_id=None, name=None, account_id=None, accountname=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()
        service_account = ServiceAccount.get(self.session, account_id, accountname)
        if not service_account:
            return self.notfound()
        user = service_account.user

        if not self.check_access(self.session, self.current_user, service_account):
            return self.forbidden()

        form = self.get_form(group.my_permissions())
        return self.render(
            "service-account-permission-grant.html", form=form, user=user, group=group
        )

    def post(self, group_id=None, name=None, account_id=None, accountname=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()
        service_account = ServiceAccount.get(self.session, account_id, accountname)
        if not service_account:
            return self.notfound()
        user = service_account.user

        if not self.check_access(self.session, self.current_user, service_account):
            return self.forbidden()

        grantable = group.my_permissions()
        form = self.get_form(grantable)
        if not form.validate():
            return self.render(
                "service-account-permission-grant.html", form=form, user=user, group=group,
                alerts=self.get_form_alerts(form.errors)
            )

        permission = Permission.get(self.session, form.data["permission"])
        if not permission:
            return self.notfound()

        allowed = False
        for perm in grantable:
            if perm[1] == permission.name:
                if matches_glob(perm[3], form.data["argument"]):
                    allowed = True
                    break
        if not allowed:
            form.argument.errors.append(
                "The group {} does not have that permission".format(group.name))
            return self.render(
                "service-account-permission-grant.html", form=form, user=user, group=group,
                alerts=self.get_form_alerts(form.errors)
            )

        try:
            grant_permission_to_service_account(
                self.session, service_account, permission, form.data["argument"])
        except IntegrityError:
            self.session.rollback()
            return self.render(
                "service-account-permission-grant.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors)
            )

        AuditLog.log(self.session, self.current_user.id, "grant_permission",
                     "Granted permission with argument: {}".format(form.data["argument"]),
                     on_permission_id=permission.id, on_group_id=group.id,
                     on_user_id=service_account.user.id)

        return self.redirect("/groups/{}/service/{}?refresh=yes".format(
            group.name, service_account.user.username))
