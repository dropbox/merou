from grouper.constants import USER_ADMIN
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount
from grouper.service_account import can_manage_service_account, disable_service_account
from grouper.user_permissions import user_has_permission


class ServiceAccountDisable(GrouperHandler):
    @staticmethod
    def check_access(session, actor, target):
        if user_has_permission(session, actor, USER_ADMIN):
            return True
        return can_manage_service_account(session, target, actor)

    def post(self, group_id=None, name=None, account_id=None, accountname=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()
        service_account = ServiceAccount.get(self.session, account_id, accountname)
        if not service_account:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, service_account):
            return self.forbidden()

        disable_service_account(self.session, self.current_user, service_account)

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
