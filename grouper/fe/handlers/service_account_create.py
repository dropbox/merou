from sqlalchemy.exc import IntegrityError

from grouper.fe.forms import ServiceAccountCreateForm
from grouper.fe.settings import settings
from grouper.fe.util import GrouperHandler
from grouper.model_soup import Group
from grouper.models.audit_log import AuditLog
from grouper.models.user import User


class ServiceAccountCreate(GrouperHandler):
    def get(self):
        form = ServiceAccountCreateForm()
        return self.render(
            "service-account-create.html", form=form,
        )

    def post(self):
        if "@" not in self.request.arguments["name"][0]:
            self.request.arguments["name"][0] += "@" + settings.service_account_email_domain

        form = ServiceAccountCreateForm(self.request.arguments)

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

        user = User(username=form.data["name"], role_user=True)
        group = Group(groupname=form.data["name"], description=form.data["description"],
            canjoin=form.data["canjoin"])

        try:
            user.add(self.session)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            form.name.errors.append("A user with name {} already exists".format(form.data["name"]))
            return self.render(
                "service-account-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        try:
            group.add(self.session)
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            form.name.errors.append("A group with name {} already exists".format(form.data["name"]))
            return self.render(
                "service-account-create.html", form=form,
                alerts=self.get_form_alerts(form.errors)
            )

        group.add_member(self.current_user, self.current_user, "GroupCreator",
            "actioned", None, "np-owner")
        group.add_member(self.current_user, user, "Service Account",
            "actioned", None, "member")
        self.session.commit()

        AuditLog.log(self.session, self.current_user.id, 'create_group',
                     'Created new service account.', on_group_id=group.id)

        return self.redirect("/groups/{}?refresh=yes".format(group.name))
