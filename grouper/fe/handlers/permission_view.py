from grouper.fe.util import GrouperHandler
from grouper.permissions import (
    get_groups_by_permission,
    get_log_entries_by_permission,
    get_permission,
)
from grouper.user_permissions import user_is_permission_admin


class PermissionView(GrouperHandler):
    def get(self, name=None):
        # TODO: use cached data instead, add refresh to appropriate redirects.
        permission = get_permission(self.session, name)
        if not permission:
            return self.notfound()

        can_change_audit_status = user_is_permission_admin(self.session, self.current_user)
        can_disable = user_is_permission_admin(self.session, self.current_user)
        mapped_groups = get_groups_by_permission(self.session, permission)
        log_entries = get_log_entries_by_permission(self.session, permission)

        self.render(
            "permission.html", permission=permission, can_disable=can_disable,
            mapped_groups=mapped_groups, log_entries=log_entries,
            can_change_audit_status=can_change_audit_status,
        )
