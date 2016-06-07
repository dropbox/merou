from sqlalchemy.exc import IntegrityError

from grouper.constants import USER_ADMIN
from grouper.email_util import send_email
from grouper.fe.forms import UserTokenForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.model_soup import User
from grouper.models.audit_log import AuditLog
from grouper.models.user_token import UserToken
from grouper.user_token import add_new_user_token


class UserTokenAdd(GrouperHandler):
    def get(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if user.name != self.current_user.name and not (
                self.current_user.has_permission(USER_ADMIN) and user.role_user
        ):
            return self.forbidden()

        self.render("user-token-add.html", form=UserTokenForm(), user=user)

    def post(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if user.name != self.current_user.name and not (
                self.current_user.has_permission(USER_ADMIN) and user.role_user
        ):
            return self.forbidden()

        form = UserTokenForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "user-token-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        try:
            token, secret = add_new_user_token(self.session, UserToken(name=form.data["name"],
                    user=user))
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            form.name.errors.append(
                "Name already in use."
            )
            return self.render(
                "user-token-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        AuditLog.log(self.session, self.current_user.id, 'add_token',
                     'Added token: {}'.format(token.name),
                     on_user_id=user.id)

        email_context = {
                "actioner": self.current_user.name,
                "changed_user": user.name,
                "action": "added",
                }
        send_email(self.session, [user.name], 'User token created', 'user_tokens_changed',
                settings, email_context)
        return self.render("user-token-created.html", token=token, secret=secret)
