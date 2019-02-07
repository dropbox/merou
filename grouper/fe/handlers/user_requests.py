from grouper.fe.util import GrouperHandler
from grouper.models.request import Request
from grouper.user import user_requests_aggregate


class UserRequests(GrouperHandler):
    """Handle list all pending requests for a single user."""

    def get(self):
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        if limit > 9000:
            limit = 9000

        requests = user_requests_aggregate(self.session, self.current_user).order_by(
            Request.requested_at.desc()
        )

        total = requests.count()
        requests = requests.offset(offset).limit(limit)

        self.render(
            "user-requests.html", requests=requests, offset=offset, limit=limit, total=total
        )
