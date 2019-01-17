from grouper.constants import PERMISSION_AUDITOR, PERMISSION_CREATE, PERMISSION_GRANT, TAG_EDIT
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.permissions import get_all_enabled_permissions


class Help(GrouperHandler):
    def get(self):
        permissions = get_all_enabled_permissions(self.session)
        d = {permission.name: permission for permission in permissions}

        self.render("help.html",
                    how_to_get_help=settings.how_to_get_help,
                    site_docs=settings.site_docs,
                    grant_perm=d[PERMISSION_GRANT],
                    create_perm=d[PERMISSION_CREATE],
                    audit_perm=d[PERMISSION_AUDITOR],
                    tag_edit=d[TAG_EDIT])
