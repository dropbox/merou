from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import unquote

from grouper.fe.forms import ServiceAccountPermissionGrantForm
from grouper.fe.util import Alert, GrouperHandler
from grouper.usecases.grant_permission_to_service_account import GrantPermissionToServiceAccountUI

if TYPE_CHECKING:
    from grouper.entities.permission_grant import GroupPermissionGrant
    from typing import Any, Iterable


class ServiceAccountPermissionGrant(GrouperHandler, GrantPermissionToServiceAccountUI):
    def get(self, *args: Any, **kwargs: Any) -> None:
        owner: str = unquote(kwargs["name"])
        service: str = unquote(kwargs["accountname"])

        usecase = self.usecase_factory.create_grant_permission_to_service_account_usecase(
            self.current_user.username, self
        )
        if not usecase.service_account_exists_with_owner(service, owner):
            return self.notfound()
        if not usecase.can_grant_permissions_for_service_account(service):
            return self.forbidden()

        grantable = usecase.permission_grants_for_group(owner)
        form = self._get_form(grantable)
        return self.render(
            "service-account-permission-grant.html", form=form, service=service, owner=owner
        )

    def grant_permission_to_service_account_failed_invalid_argument(
        self, permission: str, argument: str, service: str, message: str
    ) -> None:
        form = self._get_form(self._grantable)
        form.argument.errors = [message]
        self._render_form_with_errors(form, service, self._owner)

    def grant_permission_to_service_account_failed_permission_denied(
        self, permission: str, argument: str, service: str, message: str
    ) -> None:
        form = self._get_form(self._grantable)
        self.render(
            "service-account-permission-grant.html",
            form=form,
            service=service,
            owner=self._owner,
            alerts=[Alert("error", message)],
        )

    def grant_permission_to_service_account_failed_permission_not_found(
        self, permission: str, service: str
    ) -> None:
        message = "Unknown permission {}".format(permission)
        form = self._get_form(self._grantable)
        form.permission.errors = [message]
        self._render_form_with_errors(form, service, self._owner)

    def grant_permission_to_service_account_failed_service_account_not_found(
        self, service: str
    ) -> None:
        self.notfound()

    def granted_permission_to_service_account(
        self, permission: str, argument: str, service: str
    ) -> None:
        url = "/groups/{}/service/{}?refresh=yes".format(self._owner, service)
        self.redirect(url)

    def post(self, *args: Any, **kwargs: Any) -> None:
        self._owner: str = unquote(kwargs["name"])
        service: str = unquote(kwargs["accountname"])

        usecase = self.usecase_factory.create_grant_permission_to_service_account_usecase(
            self.current_user.username, self
        )
        if not usecase.service_account_exists_with_owner(service, self._owner):
            return self.notfound()
        self._grantable = usecase.permission_grants_for_group(self._owner)
        form = self._get_form(self._grantable)
        if not form.validate():
            return self._render_form_with_errors(form, service, self._owner)

        usecase.grant_permission_to_service_account(
            form.data["permission"], form.data["argument"], service
        )

    def _get_form(
        self, grantable: Iterable[GroupPermissionGrant]
    ) -> ServiceAccountPermissionGrantForm:
        """Helper to create a ServiceAccountPermissionGrantForm.

        Populate it with all the grantable permissions.  Note that the first choice is blank so the
        first permission alphabetically isn't always selected.

        Returns:
            ServiceAccountPermissionGrantForm object.
        """
        form = ServiceAccountPermissionGrantForm(self.request.arguments)
        form.permission.choices = [["", "(select one)"]]
        for grant in grantable:
            entry = "{} ({})".format(grant.permission, grant.argument)
            form.permission.choices.append([grant.permission, entry])
        return form

    def _render_form_with_errors(
        self, form: ServiceAccountPermissionGrantForm, service: str, owner: str
    ) -> None:
        self.render(
            "service-account-permission-grant.html",
            form=form,
            service=service,
            owner=owner,
            alerts=self.get_form_alerts(form.errors),
        )
