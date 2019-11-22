from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.constants import USER_ADMIN
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount
from grouper.service_account import can_manage_service_account, disable_service_account
from grouper.user_permissions import user_has_permission

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.models.user import User
    from typing import Any


class ServiceAccountDisable(GrouperHandler):
    @staticmethod
    def check_access(session: Session, actor: User, target: ServiceAccount) -> bool:
        if user_has_permission(session, actor, USER_ADMIN):
            return True
        return can_manage_service_account(session, target, actor)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")
        accountname = self.get_path_argument("accountname")

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()
        service_account = ServiceAccount.get(self.session, name=accountname)
        if not service_account:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, service_account):
            return self.forbidden()

        disable_service_account(self.session, self.current_user, service_account)

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
