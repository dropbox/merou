from typing import TYPE_CHECKING

from grouper.audit import get_group_audit_members_infos
from grouper.fe.handlers.template_variables import get_role_user_view_template_vars
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.models.user import User

if TYPE_CHECKING:
    from typing import Any, Optional


class RoleUserView(GrouperHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        user_id = kwargs.get("user_id")  # type: Optional[int]
        name = kwargs.get("name")  # type: Optional[str]

        self.handle_refresh()
        user = User.get(self.session, user_id, name)

        if not user or not user.role_user:
            return self.notfound()

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()
        actor = self.current_user
        graph = self.graph
        session = self.session
        self.render(
            "role-user.html",
            user=user,
            group=group,
            audit_members_infos=get_group_audit_members_infos(self.session, group),
            **get_role_user_view_template_vars(session, actor, user, group, graph)
        )
