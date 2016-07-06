from grouper.fe.util import GrouperHandler
from grouper.model_soup import User
from grouper.models.audit_log import AuditLog
from grouper.models.user_password import UserPassword
from grouper.service_account import can_manage_service_account
from grouper.user_password import delete_user_password, PasswordDoesNotExist
from grouper.user_permissions import user_is_user_admin


class UserPasswordDelete(GrouperHandler):

    @staticmethod
    def check_access(session, actor, target):
        return (actor.name == target.name or user_is_user_admin(session, actor) or
            (target.role_user and can_manage_service_account(session, actor, tuser=target)))

    def get(self, user_id=None, name=None, pass_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()
        password = UserPassword.get(self.session, user=user, id=pass_id)
        return self.render("user-password-delete.html", user=user, password=password)

    def post(self, user_id=None, name=None, pass_id=None):
        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        password = UserPassword.get(self.session, user=user, id=pass_id)

        try:
            delete_user_password(self.session, password.name, user.id)
        except PasswordDoesNotExist:
            # if the password doesn't exist, we can pretend like it did and that we deleted it
            return self.redirect("/users/{}?refresh=yes".format(user.id))
        AuditLog.log(self.session, self.current_user.id, 'delete_password',
                     'Deleted password: {}'.format(password.name),
                     on_user_id=user.id)
        self.session.commit()
        return self.redirect("/users/{}?refresh=yes".format(user.id))
