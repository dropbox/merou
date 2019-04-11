from typing import TYPE_CHECKING

from grouper.fe.forms import ServiceAccountCreateForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.service_account import (
    BadMachineSet,
    can_create_service_account,
    create_service_account,
    DuplicateServiceAccount,
)

if TYPE_CHECKING:
    from typing import Any, Optional


class ServiceAccountCreate(GrouperHandler):
    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        group_id = kwargs.get("group_id")  # type: Optional[str]
        name = kwargs.get("name")  # type: Optional[str]

        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if not can_create_service_account(self.session, self.current_user, group):
            return self.forbidden()

        form = ServiceAccountCreateForm()
        return self.render("service-account-create.html", form=form, group=group)

    def post(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        group_id = kwargs.get("group_id")  # type: Optional[str]
        name = kwargs.get("name")  # type: Optional[str]

        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if "@" not in self.request.arguments["name"][0].decode():
            self.request.arguments["name"][0] += (
                "@" + settings.service_account_email_domain
            ).encode()

        if not can_create_service_account(self.session, self.current_user, group):
            return self.forbidden()

        form = ServiceAccountCreateForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "service-account-create.html",
                form=form,
                group=group,
                alerts=self.get_form_alerts(form.errors),
            )

        if form.data["name"].split("@")[-1] != settings.service_account_email_domain:
            form.name.errors.append(
                "All service accounts must have a username ending in {}".format(
                    settings.service_account_email_domain
                )
            )
            return self.render(
                "service-account-create.html",
                form=form,
                group=group,
                alerts=self.get_form_alerts(form.errors),
            )

        try:
            create_service_account(
                self.session,
                self.current_user,
                form.data["name"],
                form.data["description"],
                form.data["machine_set"],
                group,
            )
        except DuplicateServiceAccount:
            form.name.errors.append("A user with name {} already exists".format(form.data["name"]))
        except BadMachineSet as e:
            form.machine_set.errors.append(str(e))

        if form.name.errors or form.machine_set.errors:
            return self.render(
                "service-account-create.html",
                form=form,
                group=group,
                alerts=self.get_form_alerts(form.errors),
            )

        url = "/groups/{}/service/{}?refresh=yes".format(group.name, form.data["name"])
        return self.redirect(url)
