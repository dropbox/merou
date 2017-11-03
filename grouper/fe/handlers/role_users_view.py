from grouper.fe.util import GrouperHandler


class RoleUsersView(GrouperHandler):
    def get(self):
        self.redirect("/users?service=1")
