from grouper.fe.util import GrouperHandler
from grouper.models import AuditLog, User, UserToken


class UserTokenDisable(GrouperHandler):
    def get(self, user_id=None, name=None, token_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()
        token = UserToken.get(self.session, user=user, id=token_id)
        return self.render("user-token-disable.html", user=user, token=token)

    def post(self, user_id=None, name=None, token_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if (user.name != self.current_user.name) and not self.current_user.user_admin:
            return self.forbidden()

        token = UserToken.get(self.session, user=user, id=token_id)
        token.disable()
        AuditLog.log(self.session, self.current_user.id, 'disable_token',
                     'Disabled token: {}'.format(token.name),
                     on_user_id=user.id)
        self.session.commit()
        return self.render("user-token-disabled.html", token=token)
