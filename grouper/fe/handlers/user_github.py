from typing import TYPE_CHECKING

from grouper.constants import USER_METADATA_GITHUB_USERNAME_KEY
from grouper.fe.forms import UserGitHubForm
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.user_metadata import set_user_metadata

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Any, Optional


class UserGitHub(GrouperHandler):
    @staticmethod
    def check_access(session, actor, target):
        # type: (Session, User, User) -> bool
        return actor.name == target.name

    def get(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        user_id = kwargs.get("user_id")  # type: Optional[int]
        name = kwargs.get("name")  # type: Optional[str]

        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        form = UserGitHubForm()

        self.render("user-github.html", form=form, user=user)

    def post(self, *args, **kwargs):
        # type: (*Any, **Any) -> None
        user_id = kwargs.get("user_id")  # type: Optional[int]
        name = kwargs.get("name")  # type: Optional[str]

        user = User.get(self.session, user_id, name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        form = UserGitHubForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "user-github.html", form=form, user=user, alerts=self.get_form_alerts(form.errors)
            )

        new_username = form.data["username"]
        if new_username == "":
            new_username = None
        set_user_metadata(self.session, user.id, USER_METADATA_GITHUB_USERNAME_KEY, new_username)

        AuditLog.log(
            self.session,
            self.current_user.id,
            "changed_github_username",
            "Changed GitHub username: {!r}".format(form.data["username"]),
            on_user_id=user.id,
        )

        return self.redirect("/users/{}?refresh=yes".format(user.name))
