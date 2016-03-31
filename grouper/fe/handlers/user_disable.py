from grouper.constants import USER_ADMIN, USER_DISABLE
from grouper.fe.util import GrouperHandler
from grouper.model_soup import User
from grouper.models.audit_log import AuditLog


class UserDisable(GrouperHandler):
    @staticmethod
    def check_access(actor, target):
        return (
            actor.has_permission(USER_ADMIN) or
            actor.has_permission(USER_DISABLE, argument=target.name)
        )

    def post(self, user_id=None, name=None):

        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.current_user, user):
            return self.forbidden()

        user.disable()
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'disable_user',
                     'Disabled user.', on_user_id=user.id)

        return self.redirect("/users/{}?refresh=yes".format(user.name))
