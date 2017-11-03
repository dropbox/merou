from grouper.fe.handlers.template_variables import get_role_user_view_template_vars
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.models.user import User


class RoleUserView(GrouperHandler):

    def get(self, user_id=None, name=None):
        self.handle_refresh()
        user = User.get(self.session, user_id, name)

        if not user or not user.role_user:
            return self.notfound()

        group = Group.get(self.session, name=name)
        actor = self.current_user
        graph = self.graph
        session = self.session
        self.render("service.html",
                    user=user,
                    group=group,
                    **get_role_user_view_template_vars(session, actor, user, group, graph)
                    )
