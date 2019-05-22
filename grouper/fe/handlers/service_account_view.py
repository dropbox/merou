from typing import TYPE_CHECKING

from grouper.fe.handlers.template_variables import get_user_view_template_vars
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount

if TYPE_CHECKING:
    from typing import Any, Optional


class ServiceAccountView(GrouperHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        group_id = kwargs.get("group_id")  # type: Optional[int]
        name = kwargs.get("name")  # type: Optional[str]
        account_id = kwargs.get("account_id")  # type: Optional[int]
        accountname = kwargs.get("accountname")  # type: Optional[str]

        self.handle_refresh()
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()
        service_account = ServiceAccount.get(self.session, account_id, accountname)
        if not service_account:
            return self.notfound()

        user = service_account.user
        self.render(
            "service-account.html",
            service_account=service_account,
            group=group,
            user=user,
            **get_user_view_template_vars(self.session, self.current_user, user, self.graph)
        )
