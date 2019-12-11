from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.forms import ServiceAccountCreateForm
from grouper.fe.templates import ServiceAccountCreateTemplate
from grouper.fe.util import GrouperHandler
from grouper.usecases.create_service_account import CreateServiceAccountUI

if TYPE_CHECKING:
    from typing import Any


class ServiceAccountCreate(GrouperHandler, CreateServiceAccountUI):
    def create_service_account_failed_already_exists(self, service: str, owner: str) -> None:
        error = f"A user or service account with name {service} already exists"
        self._form.name.errors.append(error)
        self._render_template(self._form, owner)

    def create_service_account_failed_invalid_name(
        self, service: str, owner: str, message: str
    ) -> None:
        self._form.name.errors.append(message)
        self._render_template(self._form, owner)

    def create_service_account_failed_invalid_machine_set(
        self, service: str, owner: str, machine_set: str, message: str
    ) -> None:
        self._form.machine_set.errors.append(message)
        self._render_template(self._form, owner)

    def create_service_account_failed_invalid_owner(self, service: str, owner: str) -> None:
        self.notfound()

    def create_service_account_failed_permission_denied(self, service: str, owner: str) -> None:
        self.forbidden()

    def created_service_account(self, service: str, owner: str) -> None:
        self.redirect(f"/groups/{owner}/service/{service}?refresh=yes")

    def get(self, *args: Any, **kwargs: Any) -> None:
        owner = self.get_path_argument("name")

        usecase = self.usecase_factory.create_create_service_account_usecase(
            self.current_user.username, self
        )
        if not usecase.can_create_service_account(owner):
            self.forbidden()
            return

        form = ServiceAccountCreateForm()
        self._render_template(form, owner)

    def post(self, *args: Any, **kwargs: Any) -> None:
        owner = self.get_path_argument("name")

        # Save the form in the handler object so that it can be reused in failure handlers.
        self._form = ServiceAccountCreateForm(self.request.arguments)
        if not self._form.validate():
            self._render_template(self._form, owner)
            return

        usecase = self.usecase_factory.create_create_service_account_usecase(
            self.current_user.username, self
        )
        usecase.create_service_account(
            self._form.data["name"],
            owner,
            self._form.data["machine_set"],
            self._form.data["description"],
        )

    def _render_template(self, form: ServiceAccountCreateForm, owner: str) -> None:
        template = ServiceAccountCreateTemplate(form=form, owner=owner)
        self.render_template_class(template)
