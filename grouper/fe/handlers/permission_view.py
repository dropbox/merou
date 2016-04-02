from grouper.fe.util import GrouperHandler
from grouper.permissions import get_groups_by_permission, get_log_entries_by_permission
from grouper.models.permission import Permission


class PermissionView(GrouperHandler):
    def get(self, name=None):
        # TODO: use cached data instead, add refresh to appropriate redirects.
        permission = Permission.get(self.session, name)
        if not permission:
            return self.notfound()

        can_delete = self.current_user.permission_admin
        mapped_groups = get_groups_by_permission(self.session, permission)
        log_entries = get_log_entries_by_permission(self.session, permission)

        self.render(
            "permission.html", permission=permission, can_delete=can_delete,
            mapped_groups=mapped_groups, log_entries=log_entries,
        )
