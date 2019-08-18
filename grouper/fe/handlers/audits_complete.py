from six import itervalues

from grouper.audit import get_audits, get_group_audit_members_count, get_group_audit_members_infos
from grouper.constants import PERMISSION_AUDITOR
from grouper.email_util import cancel_async_emails
from grouper.fe.util import Alert, GrouperHandler
from grouper.models.audit import Audit
from grouper.models.audit_log import AuditLog, AuditLogCategory
from grouper.models.audit_member import AUDIT_STATUS_CHOICES
from grouper.plugin.exceptions import PluginRejectedGroupMembershipUpdate
from grouper.user_permissions import user_has_permission


class AuditsComplete(GrouperHandler):
    def post(self, audit_id):
        if not user_has_permission(self.session, self.current_user, PERMISSION_AUDITOR):
            return self.forbidden()

        audit = self.session.query(Audit).filter(Audit.id == audit_id).one()

        # only owners can complete
        owner_ids = {member.id for member in itervalues(audit.group.my_owners())}
        if self.current_user.id not in owner_ids:
            return self.forbidden()

        if audit.complete:
            return self.redirect("/groups/{}".format(audit.group.name))

        edges = {}
        for argument in self.request.arguments:
            if argument.startswith("audit_"):
                edges[int(argument.split("_")[1])] = self.request.arguments[argument][0].decode()

        audit_members_infos = get_group_audit_members_infos(self.session, audit.group)
        for ami in audit_members_infos:
            if ami.audit_member_obj.id in edges:
                # You can only approve yourself (otherwise you can remove yourself
                # from the group and leave it ownerless)
                if ami.audit_member_obj.id == self.current_user.id:
                    ami.audit_member_obj.status = "approved"
                elif edges[ami.audit_member_obj.id] in AUDIT_STATUS_CHOICES:
                    ami.audit_member_obj.status = edges[ami.audit_member_obj.id]

        self.session.commit()

        # If there are still pending statuses, then redirect to the group page.
        if get_group_audit_members_count(self.session, audit.group, "pending"):
            return self.redirect("/groups/{}".format(audit.group.name))

        # Complete audits have to be "enacted" now. This means anybody marked as remove has to
        # be removed from the group now.
        try:
            audit_members_infos = get_group_audit_members_infos(self.session, audit.group)
            for ami in audit_members_infos:
                member_obj = ami.member_obj
                if ami.audit_member_obj.status == "remove":
                    audit.group.revoke_member(
                        self.current_user, member_obj, "Revoked as part of audit."
                    )
                    AuditLog.log(
                        self.session,
                        self.current_user.id,
                        "remove_member",
                        "Removed membership in audit: {}".format(member_obj.name),
                        on_group_id=audit.group.id,
                        on_user_id=member_obj.id,
                        category=AuditLogCategory.audit,
                    )
        except PluginRejectedGroupMembershipUpdate as e:
            alert = Alert("danger", str(e))
            return self.redirect("/groups/{}".format(audit.group.name), alerts=[alert])

        audit.complete = True
        self.session.commit()

        # Now cancel pending emails
        cancel_async_emails(self.session, "audit-{}".format(audit.group.id))

        AuditLog.log(
            self.session,
            self.current_user.id,
            "complete_audit",
            "Completed group audit.",
            on_group_id=audit.group.id,
            category=AuditLogCategory.audit,
        )

        # check if all audits are complete
        if get_audits(self.session, only_open=True).count() == 0:
            AuditLog.log(
                self.session,
                self.current_user.id,
                "complete_global_audit",
                "last open audit have been completed",
                category=AuditLogCategory.audit,
            )

        return self.redirect("/groups/{}".format(audit.group.name))
