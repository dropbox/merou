from typing import TYPE_CHECKING

from grouper.audit import get_group_audit_members_infos
from grouper.fe.handlers.template_variables import get_group_view_template_vars
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.role_user import is_role_user

if TYPE_CHECKING:
    from typing import Any, Optional


class GroupView(GrouperHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        group_id = kwargs.get("group_id")  # type: Optional[int]
        name = kwargs.get("name")  # type: Optional[str]

        self.handle_refresh()
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if is_role_user(self.session, group=group):
            return self.redirect("/service/{}".format(group.groupname))

        self.render(
            "group.html",
            group=group,
            audit_members_infos=get_group_audit_members_infos(self.session, group),
            **get_group_view_template_vars(self.session, self.current_user, group, self.graph)
        )
