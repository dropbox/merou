from sqlalchemy.exc import IntegrityError

from grouper.fe.forms import RoleUserCreateForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.role_user import create_role_user


class RoleUserCreate(GrouperHandler):
    def get(self):
        form = RoleUserCreateForm()
        return self.render(
            "service-account-create.html", form=form,
        )

    def post(self):
        if "@" not in self.request.arguments["name"][0]:
            self.request.arguments["name"][0] += "@" + settings.service_account_email_domain

        form = RoleUserCreateForm(self.request.arguments)

        if not form.validate():
            return self.render(
                "service-account-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        if form.data["name"].split("@")[-1] != settings.service_account_email_domain:
            form.name.errors.append("All service accounts must have a username ending in {}"
                .format(settings.service_account_email_domain))
            return self.render(
                "service-account-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        try:
            create_role_user(self.session, self.current_user, form.data["name"],
                form.data["description"], form.data["canjoin"])
        except IntegrityError:
            self.session.rollback()
            form.name.errors.append("A user or group with name {} already exists"
                                    .format(form.data["name"]))
            return self.render(
                "service-account-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        return self.redirect("/service/{}?refresh=yes".format(form.data["name"]))
