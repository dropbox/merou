from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.fe.handlers.template_variables import get_user_view_template_vars
from grouper.fe.util import GrouperHandler
from grouper.models.user import User

if TYPE_CHECKING:
    from typing import Any


class UserView(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        self.handle_refresh()

        user = User.get(self.session, name=name)

        if not user:
            return self.notfound()

        if user.role_user:
            return self.redirect("/service/{}".format(name))

        if user.is_service_account:
            service_account = user.service_account
            if service_account.owner:
                return self.redirect(
                    "/groups/{}/service/{}".format(service_account.owner.group.name, user.username)
                )
            else:
                self.render(
                    "service-account.html",
                    service_account=service_account,
                    group=None,
                    user=user,
                    **get_user_view_template_vars(
                        self.session, self.current_user, user, self.graph
                    ),
                )
                return

        self.render(
            "user.html",
            user=user,
            **get_user_view_template_vars(self.session, self.current_user, user, self.graph),
        )
