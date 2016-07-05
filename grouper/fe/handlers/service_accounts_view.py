from grouper.fe.util import GrouperHandler
from grouper.models.user import User


class ServiceAccountsView(GrouperHandler):
    def get(self):
        self.redirect("/users?service=1")
