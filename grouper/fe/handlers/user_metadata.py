from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.constants import USER_METADATA_GITHUB_USERNAME_KEY, USER_METADATA_SHELL_KEY
from grouper.fe.forms import UserMetadataForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.role_user import can_manage_role_user
from grouper.service_account import can_manage_service_account
from grouper.user_metadata import get_user_metadata_by_key, set_user_metadata

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Any


DEFAULT_METADATA_OPTIIONS = [
    ["n/a", "No values have been setup by the administrator for this metadata item"]
]


class UserMetadata(GrouperHandler):
    @staticmethod
    def check_access(session: Session, actor: User, target: User) -> bool:
        return (
            actor.name == target.name
            or (target.role_user and can_manage_role_user(session, actor, tuser=target))
            or (target.is_service_account and can_manage_service_account(session, target, actor))
        )

    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        metadata_key = self.get_path_argument("key")

        if metadata_key == USER_METADATA_SHELL_KEY:
            return self.redirect("/users/{}/shell".format(user.name))
        elif metadata_key == USER_METADATA_GITHUB_USERNAME_KEY:
            return self.redirect("/github/link_begin/{}".format(user.id))

        known_field = metadata_key in settings().metadata_options
        metadata_item = get_user_metadata_by_key(self.session, user.id, metadata_key)
        if not metadata_item and not known_field:
            return self.notfound()

        form = UserMetadataForm()
        form.value.choices = settings().metadata_options.get(
            metadata_key, DEFAULT_METADATA_OPTIIONS
        )

        self.render(
            "user-metadata.html",
            form=form,
            user=user,
            is_enabled=known_field,
            metadata_key=metadata_key,
        )

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        metadata_key = self.get_path_argument("key")

        if metadata_key == USER_METADATA_SHELL_KEY:
            return self.redirect("/users/{}/shell".format(user.name))
        elif metadata_key == USER_METADATA_GITHUB_USERNAME_KEY:
            return self.redirect("/github/link_begin/{}".format(user.id))

        known_field = metadata_key in settings().metadata_options
        metadata_item = get_user_metadata_by_key(self.session, user.id, metadata_key)
        if not metadata_item and not known_field:
            return self.notfound()

        form = UserMetadataForm(self.request.arguments)
        form.value.choices = settings().metadata_options.get(
            metadata_key, DEFAULT_METADATA_OPTIIONS
        )
        if not form.validate():
            return self.render(
                "user-metadata.html",
                form=form,
                user=user,
                metadata_key=metadata_key,
                is_enabled=known_field,
                alerts=self.get_form_alerts(form.errors),
            )

        set_user_metadata(self.session, user.id, metadata_key, form.data["value"])

        AuditLog.log(
            self.session,
            self.current_user.id,
            "changed_user_metadata",
            "Changed {}: {}".format(metadata_key, form.data["value"]),
            on_user_id=user.id,
        )

        return self.redirect("/users/{}?refresh=yes".format(user.name))
