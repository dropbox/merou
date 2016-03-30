from grouper.constants import USER_ADMIN, USER_ENABLE
from grouper.fe.forms import UserEnableForm
from grouper.fe.util import GrouperHandler
from grouper.model_soup import AuditLog, User


class UserEnable(GrouperHandler):
    @staticmethod
    def check_access(actor, target):
        return (
            actor.has_permission(USER_ADMIN) or
            actor.has_permission(USER_ENABLE, argument=target.name)
        )

    def post(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.current_user, user):
            return self.forbidden()

        form = UserEnableForm(self.request.arguments)
        if not form.validate():
            # TODO: add error message
            return self.redirect("/users/{}?refresh=yes".format(user.name))

        user.enable(self.current_user, preserve_membership=form.preserve_membership.data)
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'enable_user',
                     'Enabled user.', on_user_id=user.id)

        return self.redirect("/users/{}?refresh=yes".format(user.name))
