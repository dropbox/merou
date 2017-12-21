from grouper.email_util import send_email
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.public_key import delete_public_key, get_public_key, KeyNotFound
from grouper.role_user import can_manage_role_user
from grouper.service_account import can_manage_service_account
from grouper.user_permissions import user_is_user_admin


class PublicKeyDelete(GrouperHandler):

    @staticmethod
    def check_access(session, actor, target):
        return (actor.name == target.name or user_is_user_admin(session, actor) or
            (target.role_user and can_manage_role_user(session, actor, tuser=target)) or
            (target.is_service_account and can_manage_service_account(session, target, actor)))

    def get(self, user_id=None, name=None, key_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        try:
            key = get_public_key(self.session, user.id, key_id)
        except KeyNotFound:
            return self.notfound()

        self.render("public-key-delete.html", user=user, key=key)

    def post(self, user_id=None, name=None, key_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        try:
            key = get_public_key(self.session, user.id, key_id)
            delete_public_key(self.session, user.id, key_id)
        except KeyNotFound:
            return self.notfound()

        AuditLog.log(self.session, self.current_user.id, 'delete_public_key',
                     'Deleted public key: {}'.format(key.fingerprint_sha256),
                     on_user_id=user.id)

        email_context = {
                "actioner": self.current_user.name,
                "changed_user": user.name,
                "action": "removed",
                }
        send_email(self.session, [user.name], 'Public SSH key removed', 'ssh_keys_changed',
                settings, email_context)

        return self.redirect("/users/{}?refresh=yes".format(user.name))
