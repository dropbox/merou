from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.email_util import cancel_async_emails
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.role_user import is_role_user
from grouper.user import user_role

if TYPE_CHECKING:
    from typing import Any


class GroupDisable(GrouperHandler):
    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not user_role(self.current_user, members) in ("owner", "np-owner"):
            return self.forbidden()

        # Enabling and disabling service accounts via the group endpoints is forbidden
        # because we need the preserve_membership data that is only available via the
        # UserEnable form.
        if is_role_user(self.session, group=group):
            return self.forbidden()

        group.disable()

        self.session.commit()

        AuditLog.log(
            self.session,
            self.current_user.id,
            "disable_group",
            "Disabled group.",
            on_group_id=group.id,
        )

        if group.audit:
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

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
