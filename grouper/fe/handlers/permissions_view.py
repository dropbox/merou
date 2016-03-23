from grouper.fe.util import GrouperHandler


class PermissionsView(GrouperHandler):
    '''
    Controller for viewing the major permissions list. There is no privacy here; the existence of
    a permission is public.
    '''
    def get(self, audited_only=False):
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        audited_only = bool(int(self.get_argument("audited", 0)))
        if limit > 9000:
            limit = 9000

        permissions = self.graph.get_permissions(audited=audited_only)
        total = len(permissions)
        permissions = permissions[offset:offset + limit]

        can_create = self.current_user.my_creatable_permissions()

        self.render(
            "permissions.html", permissions=permissions, offset=offset, limit=limit, total=total,
            can_create=can_create, audited_permissions=audited_only
        )
