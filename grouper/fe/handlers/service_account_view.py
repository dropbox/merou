from grouper.fe.handlers.group_view import GroupView
from grouper.fe.handlers.user_view import UserView
from grouper.fe.util import GrouperHandler
from grouper.model_soup import Group
from grouper.models.user import User
from grouper.service_account import can_manage_service_account
from grouper.user import get_log_entries_by_user


class ServiceAccountView(GrouperHandler):

    @staticmethod
    def get_template_vars(session, actor, user, group, graph):
        ret = UserView.get_template_vars(session, actor, user, graph)
        ret.update(GroupView.get_template_vars(session, actor, group, graph))
        ret["can_control"] = can_manage_service_account(session, user=actor, tuser=user)
        ret["log_entries"] = sorted(set(get_log_entries_by_user(session, user) +
            group.my_log_entries()), key=lambda x: x.log_time, reverse=True)
        return ret

    def get(self, user_id=None, name=None):
        self.handle_refresh()
        user = User.get(self.session, user_id, name)

        if not user or not user.role_user:
            return self.notfound()

        group = Group.get(self.session, name=name)
        actor = self.current_user
        self.render("service.html",
                    user=user,
                    group=group,
                    **self.get_template_vars(self.session, actor, user, group, self.graph)
                    )
