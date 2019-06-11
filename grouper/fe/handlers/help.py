from typing import TYPE_CHECKING

from grouper.constants import PERMISSION_AUDITOR, PERMISSION_CREATE, PERMISSION_GRANT
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.permissions import get_permission

if TYPE_CHECKING:
    from typing import Any


class Help(GrouperHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        self.render(
            "help.html",
            how_to_get_help=settings().how_to_get_help,
            site_docs=settings().site_docs,
            grant_perm=get_permission(self.session, PERMISSION_GRANT),
            create_perm=get_permission(self.session, PERMISSION_CREATE),
            audit_perm=get_permission(self.session, PERMISSION_AUDITOR),
        )
