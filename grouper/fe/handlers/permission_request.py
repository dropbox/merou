import json
from typing import TYPE_CHECKING

from tornado.web import HTTPError

from grouper import permissions
from grouper.audit import UserNotAuditor
from grouper.fe.alerts import Alert
from grouper.fe.forms import PermissionRequestForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.permissions import get_grantable_permissions, get_permission
from grouper.plugin.exceptions import PluginRejectedPermissionArgument
from grouper.user_group import get_groups_by_user

if TYPE_CHECKING:
    from typing import Any, Dict, Iterable, List, Optional, Tuple


class PermissionRequest(GrouperHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        form, args_by_perm = self._build_form(None)
        self.render(
            "permission-request.html",
            args_by_perm_json=json.dumps(args_by_perm),
            form=form,
            uri=self.request.uri,
        )

    def post(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        form, args_by_perm = self._build_form(self.request.arguments)

        if not form.validate():
            return self.render(
                "permission-request.html",
                args_by_perm_json=json.dumps(args_by_perm),
                form=form,
                alerts=self.get_form_alerts(form.errors),
            )

        group = Group.get(self.session, name=form.group_name.data)
        if group is None:
            raise HTTPError(status_code=400, reason="that group does not exist")

        permission = get_permission(self.session, form.permission.data)
        if permission is None:
            raise HTTPError(status_code=400, reason="that permission does not exist")

        if permission.name not in args_by_perm:
            raise HTTPError(status_code=400, reason="that permission was not in the form")

        argument = form.argument.data.strip()

        # save off request
        try:
            self.plugins.check_permission_argument(permission.name, argument)
            request = permissions.create_request(
                self.session, self.current_user, group, permission, argument, form.reason.data
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
                permission=permission.name,
                argument=argument,
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
        except PluginRejectedPermissionArgument as e:
            alerts = [Alert("danger", f"Rejected by plugin: {e}")]
        else:
            alerts = []

        if alerts:
            return self.render(
                "permission-request.html",
                args_by_perm_json=json.dumps(args_by_perm),
                form=form,
                alerts=alerts,
            )
        else:
            return self.redirect("/permissions/requests/{}".format(request.id))

    def _build_form(self, data):
        # type: (Optional[int]) -> Tuple[PermissionRequestForm, Dict[str, List[str]]]
        """Build the permission request form given the request and POST data.

        Normally all fields of the form will be editable.  But if the URL
        locks down a specific value for the group, permission, or argument,
        then the specified fields will display those values and will be
        grayed out and not editable.

        """
        session = self.session
        current_user = self.current_user

        def pairs(seq):
            # type: (Iterable[str]) -> List[Tuple[str, str]]
            return [(item, item) for item in seq]

        form = PermissionRequestForm(data)

        group_names = {g.groupname for g, e in get_groups_by_user(session, current_user)}
        args_by_perm = get_grantable_permissions(
            session, settings().restricted_ownership_permissions
        )
        permission_names = {p for p in args_by_perm}

        group_param = self.get_argument("group", None)
        if group_param is not None:
            if group_param not in group_names:
                raise HTTPError(
                    status_code=404, reason="the group name in the URL is not one you belong to"
                )
            form.group_name.choices = pairs([group_param])
            form.group_name.render_kw = {"readonly": "readonly"}
            form.group_name.data = group_param
        else:
            form.group_name.choices = pairs([""] + sorted(group_names))

        permission_param = self.get_argument("permission", None)
        if permission_param is not None:
            if permission_param not in permission_names:
                raise HTTPError(
                    status_code=404, reason="an unrecognized permission is specified in the URL"
                )
            form.permission.choices = pairs([permission_param])
            form.permission.render_kw = {"readonly": "readonly"}
            form.permission.data = permission_param
        else:
            form.permission.choices = pairs(sorted(permission_names))

        argument_param = self.get_argument("argument", "")
        if argument_param:
            form.argument.render_kw = {"readonly": "readonly"}
            form.argument.data = argument_param

        return form, args_by_perm
