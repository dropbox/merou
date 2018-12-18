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
            granters_by_arg_by_perm = None
        else:
            alerts = []
            owners_by_arg_by_perm = permissions.get_owners_by_grantable_permission(self.session)
            request_tuple, total = permissions.get_requests_by_owner(self.session,
                    self.current_user, status=form.status.data,
                    limit=form.limit.data, offset=form.offset.data,
                    owners_by_arg_by_perm=owners_by_arg_by_perm)
            granters_by_arg_by_perm = {}
            for request in request_tuple.requests:
                owners = get_owner_arg_list(self.session, request.permission, request.argument,
                                            owners_by_arg_by_perm=owners_by_arg_by_perm)
                granters_by_arg = {request.argument: owners}
                granters_by_arg_by_perm[request.permission.name] = granters_by_arg

        return self.render("permission-requests.html", form=form, request_tuple=request_tuple,
                           granters=granters_by_arg_by_perm, alerts=alerts, total=total,
                           statuses=REQUEST_STATUS_CHOICES)
