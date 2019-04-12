import json

from grouper import permissions
from grouper.audit import UserNotAuditor
from grouper.fe.forms import (
    GroupPermissionRequestDropdownForm,
    GroupPermissionRequestTextForm,
    PermissionRequestForm,
)
from grouper.fe.settings import settings
from grouper.fe.util import Alert, GrouperHandler
from grouper.models.group import Group
from grouper.permissions import get_grantable_permissions, get_permission
from grouper.user_group import get_groups_by_user
from tornado.web import HTTPError


def _build_form(request, data):
    session = request.session
    current_user = request.current_user

    group_names = {g.groupname for g, e in get_groups_by_user(session, current_user)}
    args_by_perm = get_grantable_permissions(session, settings.restricted_ownership_permissions)
    permission_names = {p for p in args_by_perm}

    group_param = request.get_argument('group', None)
    if group_param is not None:
        if group_param not in group_names:
            raise HTTPError(
                status_code=404, reason='the group name in the URL is not one you belong to'
            )
        group_choices = [group_param]
    else:
        group_choices = [""] + sorted(group_names)

    permission_param = request.get_argument('permission', None)
    if permission_param is not None:
        if permission_param not in permission_names:
            raise HTTPError(
                status_code=404, reason='an unrecognized permission is specified in the URL'
            )
        permission_choices = [permission_param]
    else:
        permission_choices = [""] + sorted(args_by_perm.keys())

    form = PermissionRequestForm(data)
    form.group_name.choices = [(c, c) for c in group_choices]
    form.permission_name.choices = [(c, c) for c in permission_choices]
    return form, args_by_perm


class PermissionRequest(GrouperHandler):
    def get(self):
        form, args_by_perm = _build_form(self, None)
        self.render(
            "permission-request.html",
            args_by_perm_json=json.dumps(args_by_perm),
            form=form,
            uri=self.request.uri,
        )

    def post(self):
        form, args_by_perm = _build_form(self, self.request.arguments)

        if not form.validate():
            return self.render(
                "permission-request.html",
                args_by_perm_json=json.dumps(args_by_perm),
                form=form,
                alerts=self.get_form_alerts(form.errors),
            )

        group = self.session.query(Group).filter(Group.groupname == form.group_name.data).first()
        assert group is not None, "our prefilled permission should exist or we have problems"

        permission = get_permission(self.session, form.permission_name.data)
        assert (permission is not None) and (
            permission.name in args_by_perm
        ), "our prefilled permission should be in the form or we have problems"

        # save off request
        try:
            request = permissions.create_request(
                self.session,
                self.current_user,
                group,
                permission,
                form.argument.data,
                form.reason.data,
            )
        except permissions.RequestAlreadyGranted:
            alerts = [Alert("danger", "This group already has this permission and argument.")]
        except permissions.RequestAlreadyExists:
            alerts = [
                Alert(
                    "danger",
                    "Request for permission and argument already exists, please wait patiently.",
                )
            ]
        except permissions.NoOwnersAvailable:
            self.log_message(
                "prefilled perm+arg have no owner",
                group_name=group.name,
                permission_name=permission.name,
                argument=form.argument.data,
            )
            alerts = [
                Alert(
                    "danger",
                    "No owners available for requested permission and argument."
                    " If this error persists please contact an adminstrator.",
                )
            ]
        except UserNotAuditor as e:
            alerts = [Alert("danger", str(e))]
        else:
            alerts = None

        if alerts:
            return self.render(
                "group-permission-request.html",
                dropdown_form=dropdown_form,
                text_form=text_form,
                group=group,
                args_by_perm_json=json.dumps(args_by_perm),
                alerts=alerts,
            )
        else:
            return self.redirect("/permissions/requests/{}".format(request.id))
