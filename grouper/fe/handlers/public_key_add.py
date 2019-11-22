from __future__ import annotations

from typing import TYPE_CHECKING

from grouper import public_key
from grouper.email_util import send_email
from grouper.fe.forms import PublicKeyForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.models.audit_log import AuditLog
from grouper.models.user import User
from grouper.role_user import can_manage_role_user
from grouper.service_account import can_manage_service_account

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Any


class PublicKeyAdd(GrouperHandler):
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

        self.render("public-key-add.html", form=PublicKeyForm(), user=user)

    def post(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        user = User.get(self.session, name=name)
        if not user:
            return self.notfound()

        if not self.check_access(self.session, self.current_user, user):
            return self.forbidden()

        form = PublicKeyForm(self.request.arguments)
        if not form.validate():
            return self.render(
                "public-key-add.html",
                form=form,
                user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        try:
            pubkey = public_key.add_public_key(self.session, user, form.data["public_key"])
        except public_key.DuplicateKey:
            form.public_key.errors.append("Key already in use. Public keys must be unique.")
        except public_key.PublicKeyParseError:
            form.public_key.errors.append("Public key appears to be invalid.")
        except public_key.BadPublicKey as e:
            form.public_key.errors.append(str(e))

        if form.public_key.errors:
            return self.render(
                "public-key-add.html",
                form=form,
                user=user,
                alerts=self.get_form_alerts(form.errors),
            )

        AuditLog.log(
            self.session,
            self.current_user.id,
            "add_public_key",
            "Added public key: {}".format(pubkey.fingerprint_sha256),
            on_user_id=user.id,
        )

        email_context = {
            "actioner": self.current_user.name,
            "changed_user": user.name,
            "action": "added",
        }
        send_email(
            self.session,
            [user.name],
            "Public SSH key added",
            "ssh_keys_changed",
            settings(),
            email_context,
        )

        return self.redirect("/users/{}?refresh=yes".format(user.name))
