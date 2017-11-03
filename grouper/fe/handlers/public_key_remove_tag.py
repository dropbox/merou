from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.public_key_tag import PublicKeyTag
from grouper.models.user import User
from grouper.public_key import get_public_key, KeyNotFound, remove_tag_from_public_key, TagNotOnKey
from grouper.role_user import can_manage_role_user
from grouper.user_permissions import user_is_user_admin


class PublicKeyRemoveTag(GrouperHandler):

    @staticmethod
    def check_access(session, actor, target):
        return (actor.name == target.name or user_is_user_admin(session, actor) or
            (target.role_user and can_manage_role_user(session, actor, tuser=target)))

    def post(self, user_id=None, name=None, key_id=None, tag_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
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
