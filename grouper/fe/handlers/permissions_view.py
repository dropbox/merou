from datetime import timedelta

from grouper.fe.util import GrouperHandler
from grouper.user_permissions import user_creatable_permissions


def _round_timestamp(timestamp):
    return timestamp - timedelta(
        seconds=timestamp.second, microseconds=timestamp.microsecond
    )


class PermissionsView(GrouperHandler):
    '''
    Controller for viewing the major permissions list. There is no privacy here; the existence of
    a permission is public.
    '''
    def get(self, audited_only=False):
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        audited_only = bool(int(self.get_argument("audited", 0)))
        sort_key = self.get_argument("sort_by", "")
        sort_dir = self.get_argument("order", "")
        if limit > 9000:
            limit = 9000

        sort_keys = {
            "name": lambda p: p.name,
            # round timestamps to the nearest minute so permissions created together will
            # show up alphabetically
            "date": lambda p: _round_timestamp(p.created_on),
        }

        if sort_key not in sort_keys:
            sort_key = "name"

        if sort_dir not in ("asc", "desc"):
            sort_dir = "asc"

        permissions = sorted(
            self.graph.get_permissions(audited=audited_only),
            key=sort_keys[sort_key],
            reverse=(sort_dir == "desc")
        )

        total = len(permissions)
        permissions = permissions[offset:offset + limit]

        can_create = user_creatable_permissions(self.session, self.current_user)

        self.render(
            "permissions.html", permissions=permissions, offset=offset, limit=limit, total=total,
            can_create=can_create, audited_permissions=audited_only,
            sort_key=sort_key, sort_dir=sort_dir
        )
