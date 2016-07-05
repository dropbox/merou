from grouper.fe.util import GrouperHandler


class ServiceAccountsView(GrouperHandler):
    def get(self):
        self.redirect("/users?service=1")
