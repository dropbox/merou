from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from grouper.constants import AUDIT_MANAGER
from grouper.email_util import send_email, send_async_email
from grouper.fe.forms import AuditCreateForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.model_soup import Audit, AuditMember, GROUP_EDGE_ROLES, Group
from grouper.models.audit_log import AuditLogCategory, AuditLog


class AuditsCreate(GrouperHandler):
    def get(self):
        user = self.get_current_user()
        if not user.has_permission(AUDIT_MANAGER):
            return self.forbidden()

        self.render(
            "audit-create.html", form=AuditCreateForm(),
        )

    def post(self):
        form = AuditCreateForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "audit-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        user = self.get_current_user()
        if not user.has_permission(AUDIT_MANAGER):
            return self.forbidden()

        # Step 1, detect if there are non-completed audits and fail if so.
        open_audits = self.session.query(Audit).filter(
            Audit.complete == False).all()
        if open_audits:
            raise Exception("Sorry, there are audits in progress.")
        ends_at = datetime.strptime(form.data["ends_at"], "%m/%d/%Y")

        # Step 2, find all audited groups and schedule audits for each.
        audited_groups = []
        for groupname in self.graph.groups:
            if not self.graph.get_group_details(groupname)["audited"]:
                continue
            group = Group.get(self.session, name=groupname)
            audit = Audit(
                group_id=group.id,
                ends_at=ends_at,
            )
            try:
                audit.add(self.session)
                self.session.flush()
            except IntegrityError:
                self.session.rollback()
                raise Exception("Failed to start the audit. Please try again.")

            # Update group with new audit
            audited_groups.append(group)
            group.audit_id = audit.id

            # Step 3, now get all members of this group and set up audit rows for those edges.
            for member in group.my_members().values():
                auditmember = AuditMember(
                    audit_id=audit.id, edge_id=member.edge_id
                )
                try:
                    auditmember.add(self.session)
                except IntegrityError:
                    self.session.rollback()
                    raise Exception("Failed to start the audit. Please try again.")

        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'start_audit',
                     'Started global audit.', category=AuditLogCategory.audit)

        # Calculate schedule of emails, basically we send emails at various periods in advance
        # of the end of the audit period.
        schedule_times = []
        not_before = datetime.utcnow() + timedelta(1)
        for days_prior in (28, 21, 14, 7, 3, 1):
            email_time = ends_at - timedelta(days_prior)
            email_time.replace(hour=17, minute=0, second=0)
            if email_time > not_before:
                schedule_times.append((days_prior, email_time))

        # Now send some emails. We do this separately/later to ensure that the audits are all
        # created. Email notifications are sent multiple times if group audits are still
        # outstanding.
        for group in audited_groups:
            mail_to = [
                member.name
                for member in group.my_users()
                if GROUP_EDGE_ROLES[member.role] in ('owner', 'np-owner')
            ]

            send_email(self.session, mail_to, 'Group Audit: {}'.format(group.name), 'audit_notice',
                    settings, {"group": group.name, "ends_at": ends_at})

            for days_prior, email_time in schedule_times:
                send_async_email(
                    self.session,
                    mail_to,
                    'Group Audit: {} - {} day(s) left'.format(group.name, days_prior),
                    'audit_notice_reminder',
                    settings,
                    {
                        "group": group.name,
                        "ends_at": ends_at,
                        "days_left": days_prior,
                    },
                    email_time,
                    async_key='audit-{}'.format(group.id),
                )

        return self.redirect("/audits")
