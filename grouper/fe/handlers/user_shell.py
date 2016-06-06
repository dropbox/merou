from grouper.constants import SHELL_MD_KEY, USER_ADMIN
from grouper.fe.forms import UserShellForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.model_soup import User
from grouper.models.audit_log import AuditLog
from grouper.models.user_metadata import UserMetadata


class UserShell(GrouperHandler):
    def get(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if user.name != self.current_user.name and not (
                self.current_user.has_permission(USER_ADMIN) and user.role_user
        ):
            return self.forbidden()

        form = UserShellForm()
        form.shell.choices = settings.shell

        self.render("user-shell.html", form=form, user=user)

    def post(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if user.name != self.current_user.name and not (
                self.current_user.has_permission(USER_ADMIN) and user.role_user
        ):
            return self.forbidden()

        form = UserShellForm(self.request.arguments)
        form.shell.choices = settings.shell
        if not form.validate():
            return self.render(
                "user-shell.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        m = self.session.query(UserMetadata).filter_by(user_id=user.id,
            data_key=SHELL_MD_KEY).scalar()
        if m:
            m.data_value = form.data["shell"]
            m.add(self.session)
        else:
            m = UserMetadata(user_id=user.id, data_key=SHELL_MD_KEY, data_value=form.data["shell"])
            m.add(self.session)
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'changed_shell',
                     'Changed shell: {}'.format(form.data["shell"]),
                     on_user_id=user.id)

        return self.redirect("/users/{}?refresh=yes".format(user.name))
