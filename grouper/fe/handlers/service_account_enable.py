from __future__ import annotations

import operator
from typing import TYPE_CHECKING

from grouper.constants import USER_ADMIN
from grouper.fe.forms import ServiceAccountEnableForm
from grouper.fe.util import GrouperHandler
from grouper.group import get_all_groups
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount
from grouper.service_account import enable_service_account
from grouper.user_permissions import user_has_permission

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.models.user import User
    from typing import Any


class ServiceAccountEnable(GrouperHandler):
    @staticmethod
    def check_access(session: Session, actor: User, target: ServiceAccount) -> bool:
        return user_has_permission(session, actor, USER_ADMIN)

    def get_form(self) -> ServiceAccountEnableForm:
        """Helper to create a ServiceAccountEnableForm populated with all groups.

        Note that the first choice is blank so the first user alphabetically
        isn't always selected.
        """
        form = ServiceAccountEnableForm(self.request.arguments)

        group_choices = [
            (group.groupname, "Group: " + group.groupname)  # (value, label)
            for group in get_all_groups(self.session)
        ]

        form.owner.choices = [("", "")] + sorted(group_choices, key=operator.itemgetter(1))

        return form

    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        service_account = ServiceAccount.get(self.session, name=name)
        if not service_account:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, service_account):
            return self.forbidden()

        form = self.get_form()
        return self.render("service-account-enable.html", form=form, user=service_account.user)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        service_account = ServiceAccount.get(self.session, name=name)
        if not service_account:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, service_account):
            return self.forbidden()

        form = self.get_form()
        if not form.validate():
            return self.render(
                "service-account-enable.html",
                form=form,
                user=service_account.user,
                alerts=self.get_form_alerts(form.errors),
            )

        owner = Group.get(self.session, name=form.data["owner"])
        if owner is None:
            form.owner.errors.append("Group not found.")
            return self.render(
                "service-account-enable.html",
                form=form,
                user=service_account.user,
                alerts=self.get_form_alerts(form.errors),
            )

        enable_service_account(self.session, self.current_user, service_account, owner)
        return self.redirect(
            "/groups/{}/service/{}?refresh=yes".format(owner.name, service_account.user.username)
        )
