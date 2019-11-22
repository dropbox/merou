from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.models.user_password import UserPassword
from grouper.role_user import can_manage_role_user
from grouper.service_account import can_manage_service_account
from grouper.user_password import delete_user_password, PasswordDoesNotExist
from grouper.user_permissions import user_is_user_admin

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Any


class UserPasswordDelete(GrouperHandler):
    @staticmethod
    def check_access(session: Session, actor: User, target: User) -> bool:
        return (
            actor.name == target.name
            or user_is_user_admin(session, actor)
            or (target.role_user and can_manage_role_user(session, actor, tuser=target))
            or (target.is_service_account and can_manage_service_account(session, target, actor))
        )

    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")
        password_id = int(self.get_path_argument("password_id"))

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()
        password = UserPassword.get(self.session, user=user, id=password_id)
        return self.render("user-password-delete.html", user=user, password=password)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")
        password_id = int(self.get_path_argument("password_id"))

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        password = UserPassword.get(self.session, user=user, id=password_id)

        try:
            delete_user_password(self.session, password.name, user.id)
        except PasswordDoesNotExist:
            # if the password doesn't exist, we can pretend like it did and that we deleted it
            return self.redirect("/users/{}?refresh=yes".format(user.username))
        AuditLog.log(
            self.session,
            self.current_user.id,
            "delete_password",
            "Deleted password: {}".format(password.name),
            on_user_id=user.id,
        )
        self.session.commit()
        return self.redirect("/users/{}?refresh=yes".format(user.username))
