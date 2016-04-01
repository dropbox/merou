from grouper import permissions
from grouper.fe.forms import PermissionRequestsForm
from grouper.fe.util import GrouperHandler
from grouper.models.base.constants import REQUEST_STATUS_CHOICES


class PermissionsRequests(GrouperHandler):
    """Allow a user to review a list of permission requests that they have."""
    def get(self):
        form = PermissionRequestsForm(self.request.arguments)
        form.status.choices = [("", "")] + [(k, k) for k in REQUEST_STATUS_CHOICES]

        if not form.validate():
            alerts = self.get_form_alerts(form.errors)
            request_tuple = None
            total = 0
        else:
            alerts = []
            request_tuple, total = permissions.get_requests_by_owner(self.session,
                    self.current_user, status=form.status.data,
                    limit=form.limit.data, offset=form.offset.data)

        return self.render("permission-requests.html", form=form, request_tuple=request_tuple,
                alerts=alerts, total=total, statuses=REQUEST_STATUS_CHOICES)
