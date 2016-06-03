from grouper.fe.util import GrouperHandler
from grouper.model_soup import User
from grouper.models.audit_log import AuditLog
from grouper.public_key import get_public_key, KeyNotFound, remove_tag_from_public_key, TagNotOnKey
from grouper.models.public_key_tag import PublicKeyTag


class PublicKeyRemoveTag(GrouperHandler):
    def post(self, user_id=None, name=None, key_id=None, tag_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        try:
            key = get_public_key(self.session, user.id, key_id)
        except KeyNotFound:
            return self.notfound()

        tag = PublicKeyTag.get(self.session, id=tag_id)

        if not tag:
            return self.notfound()

        try:
            remove_tag_from_public_key(self.session, key, tag)
        except TagNotOnKey:
            return self.redirect("/users/{}?refresh=yes".format(user.name))

        AuditLog.log(self.session, self.current_user.id, 'untag_public_key',
                     'Untagged public key: {}'.format(key.fingerprint),
                     on_tag_id=tag.id, on_user_id=user.id)

        return self.redirect("/users/{}?refresh=yes".format(user.name))
