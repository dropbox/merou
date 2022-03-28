from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.handlers.template_variables import get_user_view_template_vars
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount

if TYPE_CHECKING:
    from typing import Any


class ServiceAccountView(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")
        accountname = self.get_path_argument("accountname")

        self.handle_refresh()
        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()
        service_account = ServiceAccount.get(self.session, name=accountname)
        if not service_account:
            return self.notfound()

        # We don't need the group to be valid to find the service account, but ensure that the
        # group is the owner of the service account so that we don't generate confusing URLs and
        # broken information on the view page.
        if service_account.owner.group_id != group.id:
            return self.notfound()

        user = service_account.user
        self.render(
            "service-account.html",
            service_account=service_account,
            group=group,
            user=user,
            **get_user_view_template_vars(self.session, self.current_user, user, self.graph),
        )
