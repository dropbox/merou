from grouper.fe.util import GrouperHandler
from grouper.models.user import User


class UsersView(GrouperHandler):
    def get(self):
        # TODO: use cached users instead.
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        enabled = bool(int(self.get_argument("enabled", 1)))
        if limit > 9000:
            limit = 9000

        users = (
            self.session.query(User)
            .filter(User.enabled == enabled)
            .order_by(User.username)
        )
        total = users.count()
        users = users.offset(offset).limit(limit).all()

        self.render(
            "users.html", users=users, offset=offset, limit=limit, total=total,
            enabled=enabled,
        )
