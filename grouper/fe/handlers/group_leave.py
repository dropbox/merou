from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.group import Group
from grouper.user import user_role

if TYPE_CHECKING:
    from typing import Any


class GroupLeave(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not user_role(self.current_user, members):
            return self.forbidden()

        return self.render("group-leave.html", group=group)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        members = group.my_members()
        if not user_role(self.current_user, members):
            return self.forbidden()

        group.revoke_member(self.current_user, self.current_user, "User self-revoked.")

        AuditLog.log(
            self.session,
            self.current_user.id,
            "leave_group",
            "{} left the group.".format(self.current_user.name),
            on_group_id=group.id,
        )

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
