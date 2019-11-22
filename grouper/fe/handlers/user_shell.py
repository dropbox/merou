from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.constants import USER_METADATA_SHELL_KEY
from grouper.fe.forms import UserShellForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.role_user import can_manage_role_user
from grouper.service_account import can_manage_service_account
from grouper.user_metadata import set_user_metadata

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Any


class UserShell(GrouperHandler):
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

        form = UserShellForm()
        form.shell.choices = settings().shell

        self.render("user-shell.html", form=form, user=user)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        form = UserShellForm(self.request.arguments)
        form.shell.choices = settings().shell
        if not form.validate():
            return self.render(
                "user-shell.html", form=form, user=user, alerts=self.get_form_alerts(form.errors)
            )

        set_user_metadata(self.session, user.id, USER_METADATA_SHELL_KEY, form.data["shell"])

        AuditLog.log(
            self.session,
            self.current_user.id,
            "changed_shell",
            "Changed shell: {}".format(form.data["shell"]),
            on_user_id=user.id,
        )

        return self.redirect("/users/{}?refresh=yes".format(user.name))
