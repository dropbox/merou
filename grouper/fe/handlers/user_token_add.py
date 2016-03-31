from sqlalchemy.exc import IntegrityError
from grouper.email_util import send_email
from grouper.fe.forms import UserTokenForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.model_soup import User, UserToken
from grouper.models.audit_log import AuditLog


class UserTokenAdd(GrouperHandler):
    def get(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if user.name != self.current_user.name:
            return self.forbidden()

        self.render("user-token-add.html", form=UserTokenForm(), user=user)

    def post(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if user.name != self.current_user.name:
            return self.forbidden()

        form = UserTokenForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "user-token-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        try:
            token, secret = UserToken(name=form.data["name"], user=user).add(self.session)
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
