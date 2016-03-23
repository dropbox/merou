from grouper.fe.util import GrouperHandler


class Index(GrouperHandler):
    def get(self):
        # For now, redirect to viewing your own profile. TODO: maybe have a
        # Grouper home page where you can maybe do stuff?
        return self.redirect("/users/{}".format(self.current_user.name))
