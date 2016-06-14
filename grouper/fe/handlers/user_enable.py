from grouper.constants import USER_ADMIN, USER_ENABLE
from grouper.fe.forms import UserEnableForm
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.user import enable_user
from grouper.user_permissions import user_has_permission


class UserEnable(GrouperHandler):
    @staticmethod
    def check_access(session, actor, target):
        return (
            user_has_permission(session, actor, USER_ADMIN) or
            user_has_permission(session, actor, USER_ENABLE, argument=target.name)
        )

    def post(self, user_id=None, name=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        form = UserEnableForm(self.request.arguments)
        if not form.validate():
            # TODO: add error message
            return self.redirect("/users/{}?refresh=yes".format(user.name))

        enable_user(self.session, user, self.current_user,
            preserve_membership=form.preserve_membership.data)
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'enable_user',
                     'Enabled user.', on_user_id=user.id)

        return self.redirect("/users/{}?refresh=yes".format(user.name))
