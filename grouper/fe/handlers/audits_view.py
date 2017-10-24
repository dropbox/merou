from grouper.audit import get_audits
from grouper.constants import AUDIT_MANAGER, AUDIT_VIEWER
from grouper.fe.util import GrouperHandler
from grouper.models.audit import Audit
from grouper.models.audit_log import AuditLog, AuditLogCategory
from grouper.user_permissions import user_has_permission


class AuditsView(GrouperHandler):
    def get(self):
        user = self.get_current_user()
        if not (user_has_permission(self.session, user, AUDIT_VIEWER) or
                user_has_permission(self.session, user, AUDIT_MANAGER)):
            return self.forbidden()

        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 50))
        if limit > 200:
            limit = 200

        open_filter = self.get_argument("filter", "Open Audits")
        audits = get_audits(self.session, only_open=(open_filter == "Open Audits"))

        open_audits = any([not audit.complete for audit in audits])
        total = audits.count()
        audits = audits.offset(offset).limit(limit).all()

        open_audits = self.session.query(Audit).filter(
            Audit.complete == False).all()
        can_start = user_has_permission(self.session, user, AUDIT_MANAGER)

        # FIXME(herb): make limit selected from ui
        audit_log_entries = AuditLog.get_entries(self.session, category=AuditLogCategory.audit,
                limit=100)

        self.render(
            "audits.html", audits=audits, open_filter=open_filter, can_start=can_start,
            offset=offset, limit=limit, total=total, open_audits=open_audits,
            audit_log_entries=audit_log_entries,
        )
