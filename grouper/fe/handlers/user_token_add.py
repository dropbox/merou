from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError

from grouper.email_util import send_email
from grouper.fe.forms import UserTokenForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.models.user_token import UserToken
from grouper.role_user import can_manage_role_user
from grouper.service_account import can_manage_service_account
from grouper.user_token import add_new_user_token

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Any


class UserTokenAdd(GrouperHandler):
    @staticmethod
    def check_access(session: Session, actor: User, target: User) -> bool:
        return (
            actor.name == target.name
            or (target.role_user and can_manage_role_user(session, actor, tuser=target))
            or (target.is_service_account and can_manage_service_account(session, target, actor))
        )

    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        self.render("user-token-add.html", form=UserTokenForm(), user=user)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        form = UserTokenForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "user-token-add.html",
                form=form,
                user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        try:
            token, secret = add_new_user_token(
                self.session, UserToken(name=form.data["name"], user=user)
            )
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            form.name.errors.append("Name already in use.")
            return self.render(
                "user-token-add.html",
                form=form,
                user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        AuditLog.log(
            self.session,
            self.current_user.id,
            "add_token",
            "Added token: {}".format(token.name),
            on_user_id=user.id,
        )

        email_context = {
            "actioner": self.current_user.name,
            "changed_user": user.name,
            "action": "added",
        }
        send_email(
            self.session,
            [user.name],
            "User token created",
            "user_tokens_changed",
            settings(),
            email_context,
        )
        return self.render("user-token-created.html", token=token, secret=secret)
