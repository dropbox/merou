from grouper import public_key
from grouper.email_util import send_email
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler, paginate_results
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.plugin import get_secret_forms
from grouper.public_key import generate_key_pair
from grouper.secret import SecretRiskLevel
from grouper.secret_plugin import get_all_secrets, get_ssh_key_secret_form
from grouper.service_account import can_manage_service_account


class PublicKeyCreate(GrouperHandler):

    @staticmethod
    def check_access(session, actor, target):
        return (actor.name == target.name or
            (target.role_user and can_manage_service_account(session, actor, tuser=target)))

    def post(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        public_key_str, private_key_str = generate_key_pair(settings.default_ssh_key_type,
            settings.default_ssh_key_size)

        pubkey = public_key.add_public_key(self.session, user, public_key_str)

        AuditLog.log(self.session, self.current_user.id, 'add_public_key',
                     'Added public key: {}'.format(pubkey.fingerprint),
                     on_user_id=user.id)

        email_context = {
                "actioner": self.current_user.name,
                "changed_user": user.name,
                "action": "added",
                }
        send_email(self.session, [user.name], 'Public SSH key added', 'ssh_keys_changed',
                settings, email_context)

        all_secrets = get_all_secrets(self.session).values()
        total, offset, limit, secrets = paginate_results(self, all_secrets)

        ssh_key_secret_type, attr = get_ssh_key_secret_form()

        if ssh_key_secret_type is None:
            return self.redirect("/users/{}".format(user.name))

        self.request.arguments = {
            attr: [private_key_str],
            "name": ["{}_SSH_PRIVATE_KEY".format(user.name)],
        }

        # WTForms doesn't use default values if we pass in a non-empty dictionary apparently
        # So we manually set the type value to the correct default value

        forms = [sec.get_secrets_form_args(self.session, self.current_user,
            dict(self.request.arguments, type=[sec.__name__]))
            for sec in get_secret_forms()]

        return self.render(
            "secrets.html", secrets=secrets, forms=forms, display=ssh_key_secret_type.__name__,
            offset=offset, limit=limit, total=total, risks=SecretRiskLevel,
        )
