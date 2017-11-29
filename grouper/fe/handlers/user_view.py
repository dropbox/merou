from grouper.fe.handlers.template_variables import get_user_view_template_vars
from grouper.fe.util import GrouperHandler
from grouper.models.user import User


class UserView(GrouperHandler):

    def get(self, user_id=None, name=None):
        self.handle_refresh()
        user = User.get(self.session, user_id, name)
        if user_id is not None:
            user = self.session.query(User).filter_by(id=user_id).scalar()
        else:
            user = self.session.query(User).filter_by(username=name).scalar()

        if not user:
            return self.notfound()

        if user.role_user:
            return self.redirect("/service/{}".format(user_id or name))

        if user.is_service_account:
            service_account = user.service_account
            if service_account.owner:
                return self.redirect("/groups/{}/service/{}".format(
                    service_account.owner.group.name, user.username))
            else:
                self.render(
                    "service-account.html", service_account=service_account, group=None, user=user,
                    **get_user_view_template_vars(self.session, self.current_user, user, self.graph)
                )
                return

        self.render("user.html",
                    user=user,
                    **get_user_view_template_vars(self.session, self.current_user, user, self.graph)
                    )
