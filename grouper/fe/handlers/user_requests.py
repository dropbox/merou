from grouper.fe.util import GrouperHandler
from grouper.model_soup import Request


class UserRequests(GrouperHandler):
    """Handle list all pending requests for a single user."""
    def get(self):
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        if limit > 9000:
            limit = 9000

        requests = self.current_user.my_requests_aggregate().order_by(Request.requested_at.desc())

        total = requests.count()
        requests = requests.offset(offset).limit(limit)

        self.render("user-requests.html", requests=requests, offset=offset, limit=limit,
                total=total)
