from grouper.fe.handlers.template_variables import get_user_view_template_vars
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.models.service_account import ServiceAccount


class ServiceAccountView(GrouperHandler):
    def get(self, group_id=None, name=None, account_id=None, accountname=None):
        self.handle_refresh()
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()
        service_account = ServiceAccount.get(self.session, account_id, accountname)
        if not service_account:
            return self.notfound()

        user = service_account.user
        self.render(
            "service-account.html",
            service_account=service_account,
            group=group,
            user=user,
            **get_user_view_template_vars(self.session, self.current_user, user, self.graph)
        )
