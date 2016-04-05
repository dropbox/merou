from grouper.audit import get_audits
from grouper.constants import PERMISSION_AUDITOR
from grouper.email_util import cancel_async_emails
from grouper.fe.util import GrouperHandler
from grouper.model_soup import AUDIT_STATUS_CHOICES, Audit
from grouper.models.audit_log import AuditLogCategory, AuditLog


class AuditsComplete(GrouperHandler):
    def post(self, audit_id):
        user = self.get_current_user()
        if not user.has_permission(PERMISSION_AUDITOR):
            return self.forbidden()

        audit = self.session.query(Audit).filter(Audit.id == audit_id).one()

        # only owners can complete
        owner_ids = {member.id for member in audit.group.my_owners().values()}
        if user.id not in owner_ids:
            return self.forbidden()

        if audit.complete:
            return self.redirect("/groups/{}".format(audit.group.name))

        edges = {}
        for argument in self.request.arguments:
            if argument.startswith('audit_'):
                edges[int(argument.split('_')[1])] = self.request.arguments[argument][0]

        for member in audit.my_members():
            if member.id in edges:
                # You can only approve yourself (otherwise you can remove yourself
                # from the group and leave it ownerless)
                if member.member.id == user.id:
                    member.status = "approved"
                elif edges[member.id] in AUDIT_STATUS_CHOICES:
                    member.status = edges[member.id]

        self.session.commit()

        # Now if it's completable (no pendings) then mark it complete, else redirect them
        # to the group page.
        if not audit.completable:
            return self.redirect('/groups/{}'.format(audit.group.name))

        # Complete audits have to be "enacted" now. This means anybody marked as remove has to
        # be removed from the group now.
        for member in audit.my_members():
            if member.status == "remove":
                audit.group.revoke_member(self.current_user, member.member,
                                          "Revoked as part of audit.")
                AuditLog.log(self.session, self.current_user.id, 'remove_member',
                             'Removed membership in audit: {}'.format(member.member.name),
                             on_group_id=audit.group.id, on_user_id=member.member.id,
                             category=AuditLogCategory.audit)

        audit.complete = True
        self.session.commit()

        # Now cancel pending emails
        cancel_async_emails(self.session, 'audit-{}'.format(audit.group.id))

        AuditLog.log(self.session, self.current_user.id, 'complete_audit',
                     'Completed group audit.', on_group_id=audit.group.id,
                     category=AuditLogCategory.audit)

        # check if all audits are complete
        if get_audits(self.session, only_open=True).count() == 0:
            AuditLog.log(self.session, self.current_user.id, 'complete_global_audit',
                    'last open audit have been completed', category=AuditLogCategory.audit)

        return self.redirect('/groups/{}'.format(audit.group.name))
