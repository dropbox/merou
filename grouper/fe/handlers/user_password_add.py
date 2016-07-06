from grouper.constants import USER_ADMIN
from grouper.email_util import send_email
from grouper.fe.forms import UserPasswordForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.model_soup import User
from grouper.models.audit_log import AuditLog
from grouper.user_password import add_new_user_password, PasswordAlreadyExists


class UserPasswordAdd(GrouperHandler):
    def get(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if user.name != self.current_user.name and not (
                self.current_user.has_permission(USER_ADMIN) and user.role_user
        ):
            return self.forbidden()

        self.render("user-password-add.html", form=UserPasswordForm(), user=user)

    def post(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if user.name != self.current_user.name and not (
                self.current_user.has_permission(USER_ADMIN) and user.role_user
        ):
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
