from grouper.constants import SECRETS_ADMIN
from grouper.fe.util import Alert, form_http_verbs, GrouperHandler
from grouper.secret import SecretError, SecretRiskLevel
from grouper.secret_plugin import commit_secret, delete_secret, get_all_secrets
from grouper.user_group import get_groups_by_user
from grouper.user_permissions import user_has_permission


class SecretView(GrouperHandler):

    @staticmethod
    def check_access(session, secret, actor):
        is_owner = (secret.owner.name in
            [group.name for group, group_edge in get_groups_by_user(session, actor)])
        is_secret_admin = user_has_permission(session, actor, SECRETS_ADMIN)
        return is_owner or is_secret_admin

    def get(self, name=None):
        self.handle_refresh()
        secrets = get_all_secrets(self.session)
        if name not in secrets:
            return self.notfound()

        secret = secrets[name]

        can_edit = self.check_access(self.session, secret, self.current_user)

        form = secret.get_secrets_form(self.session, self.current_user)

        self.render(
            "secret.html", secret=secret, can_edit=can_edit, risks=SecretRiskLevel, form=form
        )

    @form_http_verbs
    def post(self, name=None):
        self.handle_refresh()
        secrets = get_all_secrets(self.session)
        if name not in secrets:
            return self.notfound()

        secret = secrets[name]

        can_edit = self.check_access(self.session, secret, self.current_user)
        if not can_edit:
            return self.forbidden()

        form = secret.get_secrets_form_args(self.session, self.current_user, self.request.arguments)

        if not form.validate():
            return self.render(
                "secret.html", form=form, secret=secret, alerts=self.get_form_alerts(form.errors),
                can_edit=can_edit, risks=SecretRiskLevel,
            )

        if form.data["name"] != name:
            msg = "You cannot change the name of secrets"
            form.name.errors.append(msg)
            return self.render(
                "secret.html", form=form, secret=secret, alerts=[Alert("danger", msg)],
                can_edit=can_edit, risks=SecretRiskLevel,
            )

        try:
            SecretRiskLevel(form.data["risk_level"])
        except ValueError as e:
            form.risk_level.errors.append(e.message)
            return self.render(
                "secret.html", form=form, secret=secret, alerts=[Alert("danger", e.message)],
                can_edit=can_edit, risks=SecretRiskLevel,
            )

        secret = secret.secret_from_form(self.session, form, new=False)

        try:
            commit_secret(self.session, secret)
        except SecretError as e:
            form.name.errors.append(
                e.message
            )
            return self.render(
                "secret.html", form=form, secret=secret, alerts=self.get_form_alerts(form.errors),
                risks=SecretRiskLevel, can_edit=can_edit,
            )

        return self.redirect("/secrets/{}?refresh=yes".format(secret.name))

    def delete(self, name=None):
        secrets = get_all_secrets(self.session)
        if name not in secrets:
            return self.notfound()

        secret = secrets[name]

        can_edit = self.check_access(self.session, secret, self.current_user)
        if not can_edit:
            return self.forbidden()

        form = secret.get_secrets_form(self.session, self.current_user)
        # Apparently if we don't validate the form, the errors are tuples, not lists
        form.validate()

        try:
            delete_secret(self.session, secret)
        except SecretError as e:
            form.name.errors.append(
                e.message
            )
            return self.render(
                "secret.html", form=form, secret=secret, alerts=self.get_form_alerts(form.errors),
                risks=SecretRiskLevel, can_edit=can_edit,
            )

        return self.redirect("/secrets")
