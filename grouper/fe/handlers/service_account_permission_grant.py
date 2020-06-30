from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.alerts import Alert
from grouper.fe.forms import ServiceAccountPermissionGrantForm
from grouper.fe.templates import ServiceAccountPermissionGrantTemplate
from grouper.fe.util import GrouperHandler
from grouper.usecases.grant_permission_to_service_account import GrantPermissionToServiceAccountUI

if TYPE_CHECKING:
    from typing import Any, List, Optional, Tuple


class ServiceAccountPermissionGrant(GrouperHandler, GrantPermissionToServiceAccountUI):
    def get(self, *args: Any, **kwargs: Any) -> None:
        owner = self.get_path_argument("name")
        service = self.get_path_argument("accountname")

        usecase = self.usecase_factory.create_grant_permission_to_service_account_usecase(
            self.current_user.username, self
        )
        if not usecase.service_account_exists_with_owner(service, owner):
            return self.notfound()

        # Edge case where if owner group has no perms, a member of it with no other ability to
        # grant perms will get a 403 trying to grant to a service account. Not a big deal.
        grantable_permissions = usecase.permissions_grantable_to_service_account(service)
        if not grantable_permissions:
            return self.forbidden()

        form = self._get_form(grantable_permissions)
        self._render_template(form, service, owner)

    def grant_permission_to_service_account_failed_invalid_argument(
        self, permission: str, argument: str, service: str, message: str
    ) -> None:
        self._form.argument.errors.append(message)
        self._render_template(self._form, service, self._owner)

    def grant_permission_to_service_account_failed_permission_denied(
        self, permission: str, argument: str, service: str, message: str
    ) -> None:
        alert = Alert("error", message)
        self._render_template(self._form, service, self._owner, [alert])

    def grant_permission_to_service_account_failed_permission_not_found(
        self, permission: str, service: str
    ) -> None:
        self._form.permission.errors.append(f"Unknown permission {permission}")
        self._render_template(self._form, service, self._owner)

    def grant_permission_to_service_account_failed_service_account_not_found(
        self, service: str
    ) -> None:
        self.notfound()

    def granted_permission_to_service_account(
        self, permission: str, argument: str, service: str
    ) -> None:
        self.redirect(f"/groups/{self._owner}/service/{service}?refresh=yes")

    def post(self, *args: Any, **kwargs: Any) -> None:
        # Stash the owner in the handler object for use in error handlers.
        self._owner = self.get_path_argument("name")
        service = self.get_path_argument("accountname")

        usecase = self.usecase_factory.create_grant_permission_to_service_account_usecase(
            self.current_user.username, self
        )
        if not usecase.service_account_exists_with_owner(service, self._owner):
            return self.notfound()

        # Stash the form in the handler object for use in error handlers.
        grantable = usecase.permissions_grantable_to_service_account(service)
        self._form = self._get_form(grantable)
        if not self._form.validate():
            return self._render_template(self._form, service, self._owner)

        usecase.grant_permission_to_service_account(
            self._form.data["permission"], self._form.data["argument"], service
        )

    def _get_form(self, grantable: List[Tuple[str, str]]) -> ServiceAccountPermissionGrantForm:
        """Helper to create a ServiceAccountPermissionGrantForm.

        Populate it with all the grantable permissions.  Note that the first choice is blank so the
        first permission alphabetically isn't always selected.

        Returns:
            ServiceAccountPermissionGrantForm object.
        """
        form = ServiceAccountPermissionGrantForm(self.request.arguments)
        form.permission.choices = [["", "(select one)"]]
        for permission, argument in grantable:
            entry = "{} ({})".format(permission, argument)
            form.permission.choices.append([permission, entry])
        return form

    def _render_template(
        self,
        form: ServiceAccountPermissionGrantForm,
        service: str,
        owner: str,
        alerts: Optional[List[Alert]] = None,
    ) -> None:
        template = ServiceAccountPermissionGrantTemplate(form=form, service=service, owner=owner)
        self.render_template_class(template, alerts)
