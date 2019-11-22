from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.counter import Counter
from grouper.models.permission_map import PermissionMap
from grouper.user_group import user_is_owner_of_group
from grouper.user_permissions import user_grantable_permissions
from grouper.util import matches_glob

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.models.user import User
    from typing import Any


class PermissionsRevoke(GrouperHandler):
    @staticmethod
    def check_access(session: Session, mapping: PermissionMap, user: User):
        user_is_owner = user_is_owner_of_group(session, mapping.group, user)

        if user_is_owner:
            return True

        grantable = user_grantable_permissions(session, user)

        for perm in grantable:
            if perm[0].name == mapping.permission.name:
                if matches_glob(perm[1], mapping.argument):
                    return True

        return False

    def get(self, *args: Any, **kwargs: Any) -> None:
        mapping_id = int(self.get_path_argument("mapping_id"))
        mapping = PermissionMap.get(self.session, id=mapping_id)

        if not mapping:
            return self.notfound()

        if not self.check_access(self.session, mapping, self.current_user):
            return self.forbidden()

        self.render("permission-revoke.html", mapping=mapping)

    def post(self, *args: Any, **kwargs: Any) -> None:
        mapping_id = int(self.get_path_argument("mapping_id"))
        mapping = PermissionMap.get(self.session, id=mapping_id)

        if not mapping:
            return self.notfound()

        if not self.check_access(self.session, mapping, self.current_user):
            return self.forbidden()

        permission = mapping.permission
        group = mapping.group

        mapping.delete(self.session)
        Counter.incr(self.session, "updates")
        self.session.commit()

        AuditLog.log(
            self.session,
            self.current_user.id,
            "revoke_permission",
            "Revoked permission with argument: {}".format(mapping.argument),
            on_group_id=group.id,
            on_permission_id=permission.id,
        )

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
