from sqlalchemy.exc import IntegrityError

from grouper.email_util import send_email
from grouper.fe.forms import UserTokenForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler, paginate_results
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.models.user_token import UserToken
from grouper.plugin import get_secret_forms
from grouper.secret import SecretRiskLevel
from grouper.secret_plugin import get_all_secrets, get_token_secret_form
from grouper.service_account import can_manage_service_account
from grouper.user_token import add_new_user_token


class UserTokenCreate(GrouperHandler):

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

        self.render("user-token-add.html", form=UserTokenForm(), user=user,
            action="/users/{}/tokens/create".format(user.name))

    def post(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        form = UserTokenForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "user-token-add.html", form=form, user=user,
                action="/users/{}/tokens/create".format(user.name),
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
                action="/users/{}/tokens/create".format(user.name),
                alerts=self.get_form_alerts(form.errors)
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

        all_secrets = get_all_secrets(self.session).values()
        total, offset, limit, secrets = paginate_results(self, all_secrets)

        token_secret_type, attr = get_token_secret_form()

        if token_secret_type is None:
            return self.redirect("/users/{}".format(user.name))

        self.request.arguments = {
            "name": ["{}_TOKEN_{}".format(user.name, form.data['name'])],
            attr: [secret],
        }

        # WTForms doesn't use default values if we pass in a non-empty dictionary apparently
        # So we manually set the type value to the correct default value

        forms = [sec.get_secrets_form_args(self.session, self.current_user,
            dict(self.request.arguments, type=[sec.__name__]))
            for sec in get_secret_forms()]

        return self.render(
            "secrets.html", secrets=secrets, forms=forms, display=token_secret_type.__name__,
            offset=offset, limit=limit, total=total, risks=SecretRiskLevel,
        )
