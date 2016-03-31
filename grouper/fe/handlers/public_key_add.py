from grouper import public_key
from grouper.email_util import send_email
from grouper.fe.forms import PublicKeyForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.model_soup import User
from grouper.models.audit_log import AuditLog


class PublicKeyAdd(GrouperHandler):
    def get(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        self.render("public-key-add.html", form=PublicKeyForm(), user=user)

    def post(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        form = PublicKeyForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "public-key-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        try:
            pubkey = public_key.add_public_key(self.session, user, form.data["public_key"])
        except public_key.PublicKeyParseError:
            form.public_key.errors.append(
                "Key failed to parse and is invalid."
            )
            return self.render(
                "public-key-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )
        except public_key.DuplicateKey:
            form.public_key.errors.append(
                "Key already in use. Public keys must be unique."
            )
            return self.render(
                "public-key-add.html", form=form, user=user,
                alerts=self.get_form_alerts(form.errors),
            )

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

        return self.redirect("/users/{}?refresh=yes".format(user.name))
