from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.constants import USER_ADMIN, USER_ENABLE
from grouper.fe.forms import UserEnableForm
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.role_user import enable_role_user, is_owner_of_role_user
from grouper.user import enable_user
from grouper.user_permissions import user_has_permission

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Any


class UserEnable(GrouperHandler):
    @staticmethod
    def check_access(session: Session, actor: User, target: User) -> bool:
        return user_has_permission(session, actor, USER_ADMIN) or (
            target.role_user and is_owner_of_role_user(session, actor, tuser=target)
        )

    @staticmethod
    def check_access_without_membership(session: Session, actor: User, target: User) -> bool:
        return (
            user_has_permission(session, actor, USER_ADMIN)
            or (target.role_user and is_owner_of_role_user(session, actor, tuser=target))
            or user_has_permission(session, actor, USER_ENABLE, argument=target.name)
        )

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        form = UserEnableForm(self.request.arguments)
        if not form.validate():
            # TODO: add error message
            return self.redirect("/users/{}?refresh=yes".format(user.name))

        if form.preserve_membership.data:
            if not self.check_access(self.session, self.current_user, user):
                return self.forbidden()
        else:
            if not self.check_access_without_membership(self.session, self.current_user, user):
                return self.forbidden()

        if user.role_user:
            enable_role_user(
                self.session,
                actor=self.current_user,
                preserve_membership=form.preserve_membership.data,
                user=user,
            )
        else:
            enable_user(
                self.session,
                user,
                self.current_user,
                preserve_membership=form.preserve_membership.data,
            )

        self.session.commit()

        AuditLog.log(
            self.session, self.current_user.id, "enable_user", "Enabled user.", on_user_id=user.id
        )

        return self.redirect("/users/{}?refresh=yes".format(user.name))
