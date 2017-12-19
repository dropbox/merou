from grouper.audit import assert_can_join, UserNotAuditor
from grouper.email_util import send_email
from grouper.fe.forms import GroupRequestModifyForm
from grouper.fe.settings import settings
from grouper.fe.util import Alert, GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.base.constants import REQUEST_STATUS_CHOICES
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.request import Request
from grouper.user import user_role


class GroupRequestUpdate(GrouperHandler):
    def get(self, request_id, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        my_role = user_role(self.current_user, members)
        if my_role not in ("manager", "owner", "np-owner"):
            return self.forbidden()

        request = self.session.query(Request).filter_by(id=request_id).scalar()
        if not request:
            return self.notfound()

        form = GroupRequestModifyForm(self.request.arguments)
        form.status.choices = self._get_choices(request.status)

        updates = request.my_status_updates()

        self.render(
            "group-request-update.html", group=group, request=request,
            members=members, form=form, statuses=REQUEST_STATUS_CHOICES, updates=updates
        )

    def post(self, request_id, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        members = group.my_members()
        my_role = user_role(self.current_user, members)
        if my_role not in ("manager", "owner", "np-owner"):
            return self.forbidden()

        request = self.session.query(Request).filter_by(id=request_id).scalar()
        if not request:
            return self.notfound()

        form = GroupRequestModifyForm(self.request.arguments)
        form.status.choices = self._get_choices(request.status)

        updates = request.my_status_updates()

        if not form.status.choices:
            alerts = [Alert("info", "Request has already been processed")]
            return self.render(
                "group-request-update.html", group=group, request=request,
                members=members, form=form, alerts=alerts,
                statuses=REQUEST_STATUS_CHOICES, updates=updates
            )

        if not form.validate():
            return self.render(
                "group-request-update.html", group=group, request=request,
                members=members, form=form, alerts=self.get_form_alerts(form.errors),
                statuses=REQUEST_STATUS_CHOICES, updates=updates
            )

        # We have to test this here, too, to ensure that someone can't sneak in with a pending
        # request that used to be allowed.
        if form.data["status"] != "cancelled":
            fail_message = 'This join is denied with this role at this time.'
            try:
                user_can_join = assert_can_join(request.requesting, request.get_on_behalf(),
                                                role=request.edge.role)
            except UserNotAuditor as e:
                user_can_join = False
                fail_message = e
            if not user_can_join:
                return self.render(
                    "group-request-update.html", group=group, request=request,
                    members=members, form=form, statuses=REQUEST_STATUS_CHOICES, updates=updates,
                    alerts=[
                        Alert('danger', fail_message, 'Audit Policy Enforcement')
                    ]
                )

        request.update_status(
            self.current_user,
            form.data["status"],
            form.data["reason"]
        )
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'update_request',
                     'Updated request to status: {}'.format(form.data["status"]),
                     on_group_id=group.id, on_user_id=request.requester.id)

        edge = self.session.query(GroupEdge).filter_by(
            id=request.edge_id
        ).one()

        approver_mail_to = [
            user.name
            for user in group.my_approver_users()
            if user.name != self.current_user.name and user.name != request.requester.username
        ]

        subj = "Re: " + self.render_template(
            'email/pending_request_subj.tmpl',
            group=group.name,
            user=request.requester.username
        )

        send_email(
            self.session,
            approver_mail_to,
            subj,
            "approver_request_updated",
            settings,
            {
                'group_name': group.name,
                'requester': request.requester.username,
                'changed_by': self.current_user.name,
                'status': form.data['status'],
                'role': edge.role,
                'reason': form.data['reason'],
                'references_header': request.reference_id,
            },
        )

        if form.data['status'] == 'actioned':
            send_email(
                self.session,
                [request.requester.name],
                'Added to group: {}'.format(group.groupname),
                'request_actioned',
                settings,
                {
                    'group_name': group.name,
                    'actioned_by': self.current_user.name,
                    'reason': form.data['reason'],
                    'expiration': edge.expiration,
                    'role': edge.role,
                }
            )
        elif form.data['status'] == 'cancelled':
            send_email(
                self.session,
                [request.requester.name],
                'Request to join cancelled: {}'.format(group.groupname),
                'request_cancelled',
                settings,
                {
                    'group_name': group.name,
                    'cancelled_by': self.current_user.name,
                    'reason': form.data['reason'],
                    'expiration': edge.expiration,
                    'role': edge.role,
                }
            )

        # No explicit refresh because handler queries SQL.
        if form.data['redirect_aggregate']:
            return self.redirect("/user/requests")
        else:
            return self.redirect("/groups/{}/requests".format(group.name))

    def _get_choices(self, current_status):
        return [
            [status] * 2
            for status in REQUEST_STATUS_CHOICES[current_status]
        ]
