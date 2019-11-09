from grouper import permissions
from grouper.audit import UserNotAuditor
from grouper.fe.alerts import Alert
from grouper.fe.forms import PermissionRequestUpdateForm
from grouper.fe.util import GrouperHandler
from grouper.models.base.constants import REQUEST_STATUS_CHOICES


class PermissionsRequestUpdate(GrouperHandler):
    """Allow a user to action a permisison request they have."""

    def _get_choices(self, current_status):
        return [["", ""]] + [[status] * 2 for status in REQUEST_STATUS_CHOICES[current_status]]

    def get(self, request_id):
        # check for request existence
        request = permissions.get_request_by_id(self.session, request_id)
        if not request:
            return self.notfound()

        # compile list of changes to this request
        owners_by_arg_by_perm = permissions.get_owners_by_grantable_permission(
            self.session, separate_global=True
        )
        change_comment_list = permissions.get_changes_by_request_id(self.session, request_id)
        can_approve_request = permissions.can_approve_request(
            self.session, request, self.current_user, owners_by_arg_by_perm=owners_by_arg_by_perm
        )

        approvers = []

        if not can_approve_request:
            owner_arg_list = permissions.get_owner_arg_list(
                self.session, request.permission, request.argument
            )
            all_owners = {o.groupname for o, _ in owner_arg_list}
            global_owners = {
                o.groupname for o in owners_by_arg_by_perm[permissions.GLOBAL_OWNERS]["*"]
            }
            non_global_owners = all_owners - global_owners
            approvers = non_global_owners if len(non_global_owners) else all_owners

        form = PermissionRequestUpdateForm(self.request.arguments)
        form.status.choices = self._get_choices(request.status)

        return self.render(
            "permission-request-update.html",
            form=form,
            request=request,
            change_comment_list=change_comment_list,
            statuses=REQUEST_STATUS_CHOICES,
            can_approve_request=can_approve_request,
            approvers=approvers,
        )

    def post(self, request_id):
        # check for request existence
        request = permissions.get_request_by_id(self.session, request_id)
        if not request:
            return self.notfound()

        # check that this user should be actioning this request
        user_requests, total = permissions.get_requests(
            self.session, status="pending", limit=None, offset=0, owner=self.current_user
        )
        user_request_ids = [ur.id for ur in user_requests.requests]
        if request.id not in user_request_ids:
            return self.forbidden()

        form = PermissionRequestUpdateForm(self.request.arguments)
        form.status.choices = self._get_choices(request.status)
        if not form.validate():
            change_comment_list = [
                (sc, user_requests.comment_by_status_change_id[sc.id])
                for sc in user_requests.status_change_by_request_id[request.id]
            ]

            return self.render(
                "permission-request-update.html",
                form=form,
                request=request,
                change_comment_list=change_comment_list,
                statuses=REQUEST_STATUS_CHOICES,
                alerts=self.get_form_alerts(form.errors),
            )

        try:
            permissions.update_request(
                self.session, request, self.current_user, form.status.data, form.reason.data
            )
        except UserNotAuditor as e:
            alerts = [Alert("danger", str(e))]

            change_comment_list = [
                (sc, user_requests.comment_by_status_change_id[sc.id])
                for sc in user_requests.status_change_by_request_id[request.id]
            ]

            return self.render(
                "permission-request-update.html",
                form=form,
                request=request,
                change_comment_list=change_comment_list,
                statuses=REQUEST_STATUS_CHOICES,
                alerts=alerts,
            )

        return self.redirect("/permissions/requests?status=pending")
