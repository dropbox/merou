from grouper.fe.util import GrouperHandler


class NotFound(GrouperHandler):
    def get(self):
        return self.notfound()
