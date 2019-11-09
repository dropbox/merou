from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.constants import USER_ADMIN, USER_DISABLE
from grouper.email_util import cancel_async_emails
from grouper.fe.alerts import Alert
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.models.user import User
from grouper.plugin.exceptions import PluginRejectedDisablingUser
from grouper.role_user import disable_role_user, is_owner_of_role_user
from grouper.user import disable_user
from grouper.user_permissions import user_has_permission

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Any


class UserDisable(GrouperHandler):
    @staticmethod
    def check_access(session: Session, actor: User, target: User) -> bool:
        return (
            user_has_permission(session, actor, USER_ADMIN)
            or user_has_permission(session, actor, USER_DISABLE, argument=target.name)
            or (target.role_user and is_owner_of_role_user(session, actor, tuser=target))
        )

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        try:
            if user.role_user:
                disable_role_user(self.session, user=user)
            else:
                disable_user(self.session, user)
        except PluginRejectedDisablingUser as e:
            alert = Alert("danger", str(e))
            return self.redirect("/users/{}".format(user.name), alerts=[alert])

        self.session.commit()

        AuditLog.log(
            self.session,
            self.current_user.id,
            "disable_user",
            "Disabled user.",
            on_user_id=user.id,
        )

        if user.role_user:
            group = Group.get(self.session, name=user.username)
            if group and group.audit:
                # complete the audit
                group.audit.complete = True
                self.session.commit()

                cancel_async_emails(self.session, f"audit-{group.id}")

                AuditLog.log(
                    self.session,
                    self.current_user.id,
                    "complete_audit",
                    "Disabling group completes group audit.",
                    on_group_id=group.id,
                )

        return self.redirect("/users/{}?refresh=yes".format(user.name))
