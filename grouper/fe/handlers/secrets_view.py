from grouper.fe.util import Alert, GrouperHandler, paginate_results
from grouper.plugin import get_secret_forms
from grouper.secret import SecretError, SecretRiskLevel
from grouper.secret_plugin import commit_secret, get_all_secrets


class SecretsView(GrouperHandler):

    def get(self):
        self.handle_refresh()
        all_secrets = get_all_secrets(self.session).values()
        total, offset, limit, secrets = paginate_results(self, all_secrets)

        forms = [sec.get_secrets_form_args(self.session, self.current_user, self.request.arguments)
            for sec in get_secret_forms()]

        self.render(
            "secrets.html", secrets=secrets, forms=forms,
            offset=offset, limit=limit, total=total, risks=SecretRiskLevel,
        )

    def post(self):
        secret_type = [secret for secret in get_secret_forms()
            if secret.__name__ == self.request.arguments["type"][0]][0]
        form = secret_type.get_secrets_form_args(self.session, self.current_user,
            self.request.arguments)
        forms = [sec.get_secrets_form_args(self.session, self.current_user, self.request.arguments)
            for sec in get_secret_forms()]
        forms = [form if type(form) == type(f) else f for f in forms]
        all_secrets = get_all_secrets(self.session)
        total, offset, limit, secrets = paginate_results(self, all_secrets.values())

        if not form.validate():
            return self.render(
                "secrets.html", forms=forms, secrets=secrets, offset=offset, limit=limit,
                total=total, alerts=self.get_form_alerts(form.errors), risks=SecretRiskLevel,
            )

        if form.data["name"] in all_secrets:
            msg = "A secret with the name {} already exists".format(form.data["name"])
            form.name.errors.append(msg)
            return self.render(
                "secrets.html", forms=forms, secrets=secrets, offset=offset, limit=limit,
                total=total, alerts=[Alert("danger", msg)], risks=SecretRiskLevel,
            )

        try:
            SecretRiskLevel(form.data["risk_level"])
        except ValueError as e:
            form.risk_level.errors.append(e.message)
            return self.render(
                "secrets.html", forms=forms, secrets=secrets, offset=offset, limit=limit,
                total=total, alerts=[Alert("danger", e.message)], risks=SecretRiskLevel,
            )

        secret = secret_type.secret_from_form(self.session, form, new=True)

        try:
            commit_secret(self.session, secret)
        except SecretError as e:
            form.name.errors.append(
                e.message
            )
            return self.render(
                "secrets.html", forms=forms, secrets=secrets, offset=offset, limit=limit,
                total=total, alerts=self.get_form_alerts(form.errors), risks=SecretRiskLevel,
            )

        return self.redirect("/secrets/{}?refresh=yes".format(secret.name))
