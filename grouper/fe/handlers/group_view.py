from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.audit import get_group_audit_members_infos
from grouper.fe.handlers.template_variables import get_group_view_template_vars
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.role_user import is_role_user

if TYPE_CHECKING:
    from typing import Any


class GroupView(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        self.handle_refresh()
        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        if is_role_user(self.session, group=group):
            return self.redirect("/service/{}".format(group.groupname))

        self.render(
            "group.html",
            group=group,
            audit_members_infos=get_group_audit_members_infos(self.session, group),
            **get_group_view_template_vars(self.session, self.current_user, group, self.graph),
        )
