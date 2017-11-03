from grouper.fe.handlers.template_variables import get_group_view_template_vars
from grouper.fe.util import GrouperHandler
from grouper.models.group import Group
from grouper.role_user import is_role_user


class GroupView(GrouperHandler):

    def get(self, group_id=None, name=None):
        self.handle_refresh()
        group = Group.get(self.session, group_id, name)
        if not group:
            return self.notfound()

        if is_role_user(self.session, group=group):
            return self.redirect("/service/{}".format(group.groupname))

        self.render(
            "group.html", group=group,
            **get_group_view_template_vars(self.session, self.current_user, group, self.graph)
        )
