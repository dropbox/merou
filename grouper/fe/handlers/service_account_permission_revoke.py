from grouper.constants import USER_ADMIN
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.counter import Counter
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount
from grouper.models.service_account_permission_map import ServiceAccountPermissionMap
from grouper.service_account import can_manage_service_account
from grouper.user_permissions import user_has_permission


class ServiceAccountPermissionRevoke(GrouperHandler):
    @staticmethod
    def check_access(session, actor, target):
        if user_has_permission(session, actor, USER_ADMIN):
            return True
        return can_manage_service_account(session, target, actor)

    def post(self, group_id=None, name=None, account_id=None, accountname=None, mapping_id=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()
        service_account = ServiceAccount.get(self.session, account_id, accountname)
        if not service_account:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, service_account):
            return self.forbidden()

        mapping = ServiceAccountPermissionMap.get(self.session, mapping_id)
        if not mapping:
            return self.notfound()

        permission = mapping.permission
        argument = mapping.argument

        mapping.delete(self.session)
        Counter.incr(self.session, "updates")
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, "revoke_permission",
                     "Revoked permission with argument: {}".format(argument),
                     on_permission_id=permission.id, on_group_id=group.id,
                     on_user_id=service_account.user.id)

        return self.redirect("/groups/{}/service/{}?refresh=yes".format(
            group.name, service_account.user.username))
