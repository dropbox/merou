from grouper import permissions
from grouper.audit import UserNotAuditor
from grouper.fe.forms import PermissionRequestUpdateForm
from grouper.fe.util import GrouperHandler, Alert
from grouper.models.base.constants import REQUEST_STATUS_CHOICES


class PermissionsRequestUpdate(GrouperHandler):
    """Allow a user to action a permisison request they have."""
    def _get_choices(self, current_status):
        return [["", ""]] + [
            [status] * 2
            for status in REQUEST_STATUS_CHOICES[current_status]
        ]

    def get(self, request_id):
        # check for request existence
        request = permissions.get_request_by_id(self.session, request_id)
        if not request:
            return self.notfound()

        # check that this user should be actioning this request
        user_requests, total = permissions.get_requests_by_owner(self.session,
                self.current_user, status="pending", limit=None, offset=0)
        user_request_ids = [ur.id for ur in user_requests.requests]
        if request.id not in user_request_ids:
            return self.forbidden()

        form = PermissionRequestUpdateForm(self.request.arguments)
        form.status.choices = self._get_choices(request.status)

        # compile list of changes to this request
        change_comment_list = [(sc, user_requests.comment_by_status_change_id[sc.id]) for sc in
                user_requests.status_change_by_request_id[request.id]]

        return self.render("permission-request-update.html", form=form, request=request,
                change_comment_list=change_comment_list, statuses=REQUEST_STATUS_CHOICES)

    def post(self, request_id):
        # check for request existence
        request = permissions.get_request_by_id(self.session, request_id)
        if not request:
            return self.notfound()

        # check that this user should be actioning this request
        user_requests, total = permissions.get_requests_by_owner(self.session,
                self.current_user, status="pending", limit=None, offset=0)
        user_request_ids = [ur.id for ur in user_requests.requests]
        if request.id not in user_request_ids:
            return self.forbidden()

        form = PermissionRequestUpdateForm(self.request.arguments)
        form.status.choices = self._get_choices(request.status)
        if not form.validate():
            change_comment_list = [(sc, user_requests.comment_by_status_change_id[sc.id]) for sc in
                    user_requests.status_change_by_request_id[request.id]]

            return self.render("permission-request-update.html", form=form, request=request,
                    change_comment_list=change_comment_list, statuses=REQUEST_STATUS_CHOICES,
                    alerts=self.get_form_alerts(form.errors))

        try:
            permissions.update_request(self.session, request, self.current_user,
                    form.status.data, form.reason.data)
        except UserNotAuditor as e:
            alerts = [Alert("danger", str(e))]

            change_comment_list = [(sc, user_requests.comment_by_status_change_id[sc.id]) for sc in
                    user_requests.status_change_by_request_id[request.id]]

            return self.render("permission-request-update.html", form=form, request=request,
                    change_comment_list=change_comment_list, statuses=REQUEST_STATUS_CHOICES,
                    alerts=alerts)

        return self.redirect("/permissions/requests")
