import json
from grouper import permissions
from grouper.fe.forms import GroupPermissionRequestDropdownForm, GroupPermissionRequestTextForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler, Alert
from grouper.model_soup import Group
from grouper.permissions import get_grantable_permissions
from grouper.models.permission import Permission


class GroupPermissionRequest(GrouperHandler):
    @staticmethod
    def _get_forms(args_by_perm, data):
        dropdown_form = GroupPermissionRequestDropdownForm(data)
        text_form = GroupPermissionRequestTextForm(data)

        for form in [dropdown_form, text_form]:
            form.permission_name.choices = [("", "")] + sorted([(p, p) for p in
                    args_by_perm.keys()])

        dropdown_form.argument.choices = [("", "")]

        return dropdown_form, text_form

    def get(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        # Only members can request permissions
        if not self.current_user.is_member(group.my_members()):
            return self.forbidden()

        args_by_perm = get_grantable_permissions(self.session,
                settings.restricted_ownership_permissions)
        dropdown_form, text_form = GroupPermissionRequest._get_forms(args_by_perm, None)

        self.render("group-permission-request.html", dropdown_form=dropdown_form,
                text_form=text_form, group=group, args_by_perm_json=json.dumps(args_by_perm),
                dropdown_help=settings.permission_request_dropdown_help,
                text_help=settings.permission_request_text_help)

    def post(self, group_id=None, name=None):
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        # Only members can request permissions
        if not self.current_user.is_member(group.my_members()):
            return self.forbidden()

        # check inputs
        args_by_perm = get_grantable_permissions(self.session,
                settings.restricted_ownership_permissions)
        dropdown_form, text_form = GroupPermissionRequest._get_forms(args_by_perm,
                self.request.arguments)

        argument_type = self.request.arguments.get("argument_type")
        if argument_type and argument_type[0] == "text":
            form = text_form
        elif argument_type and argument_type[0] == "dropdown":
            form = dropdown_form
            form.argument.choices = [(a, a) for a in args_by_perm[form.permission_name.data]]
        else:
            # someone messing with the form
            self.log_message("unknown argument type", group_name=group.name,
                    argument_type=argument_type)
            return self.forbidden()

        if not form.validate():
            return self.render(
                    "group-permission-request.html", dropdown_form=dropdown_form,
                    text_form=text_form, group=group, args_by_perm_json=json.dumps(args_by_perm),
                    alerts=self.get_form_alerts(form.errors),
                    dropdown_help=settings.permission_request_dropdown_help,
                    text_help=settings.permission_request_text_help,
                    )

        permission = Permission.get(self.session, form.permission_name.data)
        assert permission is not None, "our prefilled permission should exist or we have problems"

        # save off request
        try:
            permissions.create_request(self.session, self.current_user, group,
                    permission, form.argument.data, form.reason.data)
        except permissions.RequestAlreadyGranted:
            alerts = [Alert("danger", "This group already has this permission and argument.")]
        except permissions.RequestAlreadyExists:
            alerts = [Alert("danger",
                    "Request for permission and argument already exists, please wait patiently.")]
        except permissions.NoOwnersAvailable:
            self.log_message("prefilled perm+arg have no owner", group_name=group.name,
                    permission_name=permission.name, argument=form.argument.data)
            alerts = [Alert("danger", "No owners available for requested permission and argument."
                    " If this error persists please contact an adminstrator.")]
        else:
            alerts = None

        if alerts:
            return self.render(
                    "group-permission-request.html", dropdown_form=dropdown_form,
                    text_form=text_form, group=group, args_by_perm_json=json.dumps(args_by_perm),
                    alerts=alerts,
                    )
        else:
            return self.redirect("/groups/{}".format(group.name))
