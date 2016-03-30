from grouper.fe.util import GrouperHandler
from grouper.model_soup import Permission


class PermissionView(GrouperHandler):
    def get(self, name=None):
        # TODO: use cached data instead, add refresh to appropriate redirects.
        permission = Permission.get(self.session, name)
        if not permission:
            return self.notfound()

        can_delete = self.current_user.permission_admin
        mapped_groups = permission.get_mapped_groups()
        log_entries = permission.my_log_entries()

        self.render(
            "permission.html", permission=permission, can_delete=can_delete,
            mapped_groups=mapped_groups, log_entries=log_entries,
        )
