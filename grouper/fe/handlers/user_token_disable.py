from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.models.user_token import UserToken
from grouper.role_user import can_manage_role_user
from grouper.service_account import can_manage_service_account
from grouper.user_permissions import user_is_user_admin
from grouper.user_token import disable_user_token

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Any


class UserTokenDisable(GrouperHandler):
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
        token_id = int(self.get_path_argument("token_id"))

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        token = UserToken.get(self.session, user=user, id=token_id)
        return self.render("user-token-disable.html", user=user, token=token)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")
        token_id = int(self.get_path_argument("token_id"))

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        token = UserToken.get(self.session, user=user, id=token_id)
        disable_user_token(self.session, token)
        AuditLog.log(
            self.session,
            self.current_user.id,
            "disable_token",
            "Disabled token: {}".format(token.name),
            on_user_id=user.id,
        )
        self.session.commit()
        return self.render("user-token-disabled.html", token=token)
