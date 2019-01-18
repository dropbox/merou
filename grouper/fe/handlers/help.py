from grouper.constants import PERMISSION_AUDITOR, PERMISSION_CREATE, PERMISSION_GRANT, TAG_EDIT
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.permissions import get_permission


class Help(GrouperHandler):
    def get(self):
        self.render("help.html",
                    how_to_get_help=settings.how_to_get_help,
                    site_docs=settings.site_docs,
                    grant_perm=get_permission(self.session, PERMISSION_GRANT),
                    create_perm=get_permission(self.session, PERMISSION_CREATE),
                    audit_perm=get_permission(self.session, PERMISSION_AUDITOR),
                    tag_edit=get_permission(self.session, TAG_EDIT))
