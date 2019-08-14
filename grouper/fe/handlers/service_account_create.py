from typing import TYPE_CHECKING

from grouper.fe.forms import ServiceAccountCreateForm
from grouper.fe.util import GrouperHandler
from grouper.usecases.create_service_account import CreateServiceAccountUI

if TYPE_CHECKING:
    from typing import Any


class ServiceAccountCreate(GrouperHandler, CreateServiceAccountUI):
    def render_form_with_errors(self, form, owner):
        # type: (ServiceAccountCreateForm, str) -> None
        return self.render(
            "service-account-create.html",
            form=form,
            owner=owner,
            alerts=self.get_form_alerts(form.errors),
        )

    def create_service_account_failed_already_exists(self, service, owner):
        # type: (str, str) -> None
        form = ServiceAccountCreateForm(self.request.arguments)
        msg = "A user or service account with name {} already exists".format(service)
        form.name.errors.append(msg)
        self.render_form_with_errors(form, owner)

    def create_service_account_failed_invalid_name(self, service, owner, message):
        # type: (str, str, str) -> None
        form = ServiceAccountCreateForm(self.request.arguments)
        form.name.errors = [message]
        self.render_form_with_errors(form, owner)

    def create_service_account_failed_invalid_machine_set(
        self, service, owner, machine_set, message
    ):
        # type: (str, str, str, str) -> None
        form = ServiceAccountCreateForm(self.request.arguments)
        form.machine_set.errors = [message]
        self.render_form_with_errors(form, owner)

    def create_service_account_failed_invalid_owner(self, service, owner):
        # type: (str, str) -> None
        self.notfound()

    def create_service_account_failed_permission_denied(self, service, owner):
        # type: (str, str) -> None
        self.forbidden()

    def created_service_account(self, service, owner):
        # type: (str, str) -> None
        url = "/groups/{}/service/{}?refresh=yes".format(owner, service)
        self.redirect(url)

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        owner = kwargs["name"]  # type: str

        usecase = self.usecase_factory.create_create_service_account_usecase(
            self.current_user.username, self
        )
        if not usecase.can_create_service_account(owner):
            return self.forbidden()

        form = ServiceAccountCreateForm()
        return self.render("service-account-create.html", form=form, owner=owner)

    def post(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        owner = kwargs["name"]  # type: str

        form = ServiceAccountCreateForm(self.request.arguments)
        if not form.validate():
            self.render_form_with_errors(form, owner)

        usecase = self.usecase_factory.create_create_service_account_usecase(
            self.current_user.username, self
        )
        usecase.create_service_account(
            form.data["name"], owner, form.data["machine_set"], form.data["description"]
        )
