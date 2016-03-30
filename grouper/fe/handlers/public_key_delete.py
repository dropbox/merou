from grouper.email_util import send_email
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.model_soup import AuditLog, PublicKey, User


class PublicKeyDelete(GrouperHandler):
    def get(self, user_id=None, name=None, key_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        key = self.session.query(PublicKey).filter_by(id=key_id, user_id=user.id).scalar()
        if not key:
            return self.notfound()

        self.render("public-key-delete.html", user=user, key=key)

    def post(self, user_id=None, name=None, key_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        key = self.session.query(PublicKey).filter_by(id=key_id, user_id=user.id).scalar()
        if not key:
            return self.notfound()

        key.delete(self.session)
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'delete_public_key',
                     'Deleted public key: {}'.format(key.fingerprint),
                     on_user_id=user.id)

        email_context = {
                "actioner": self.current_user.name,
                "changed_user": user.name,
                "action": "removed",
                }
        send_email(self.session, [user.name], 'Public SSH key removed', 'ssh_keys_changed',
                settings, email_context)

        return self.redirect("/users/{}?refresh=yes".format(user.name))
