from grouper.email_util import send_email
from grouper.fe.forms import UserPasswordForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.service_account import can_manage_service_account
from grouper.user_password import add_new_user_password, PasswordAlreadyExists


class UserPasswordAdd(GrouperHandler):

    @staticmethod
    def check_access(session, actor, target):
        return actor.name == target.name or (target.role_user and
            can_manage_service_account(session, actor, tuser=target))

    def get(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        self.render("user-password-add.html", form=UserPasswordForm(), user=user)

    def post(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        form = UserPasswordForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "user-password-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        pass_name = form.data["name"]
        password = form.data["password"]
        try:
            add_new_user_password(self.session, pass_name, password, user.id)
        except PasswordAlreadyExists:
            self.session.rollback()
            form.name.errors.append(
                "Name already in use."
            )
            return self.render(
                "user-password-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        AuditLog.log(self.session, self.current_user.id, 'add_password',
                     'Added password: {}'.format(pass_name),
                     on_user_id=user.id)

        email_context = {
                "actioner": self.current_user.name,
                "changed_user": user.name,
                "pass_name": pass_name,
                }
        send_email(self.session, [user.name], 'User password created', 'user_password_created',
                settings, email_context)
        return self.redirect("/users/{}?refresh=yes".format(user.name))
