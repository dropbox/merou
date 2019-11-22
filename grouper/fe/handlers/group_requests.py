from __future__ import annotations

from typing import TYPE_CHECKING

from grouper.entities.group_edge import APPROVER_ROLE_INDICES, OWNER_ROLE_INDICES
from grouper.fe.util import GrouperHandler
from grouper.group_requests import get_requests_by_group
from grouper.models.base.constants import REQUEST_STATUS_CHOICES
from grouper.models.group import Group
from grouper.models.request import Request
from grouper.user import user_role, user_role_index

if TYPE_CHECKING:
    from typing import Any


class GroupRequests(GrouperHandler):
    def get(self, *args: Any, **kwargs: Any) -> None:
        name = self.get_path_argument("name")

        group = Group.get(self.session, name=name)
        if not group:
            return self.notfound()

        status = self.get_argument("status", None)
        offset = int(self.get_argument("offset", 0))
        limit = int(self.get_argument("limit", 100))
        if limit > 9000:
            limit = 9000

        requests = get_requests_by_group(self.session, group, status=status).order_by(
            Request.requested_at.desc()
        )
        members = group.my_members()

        total = requests.count()
        requests = requests.offset(offset).limit(limit)

        current_user_role = {
            "is_owner": user_role_index(self.current_user, members) in OWNER_ROLE_INDICES,
            "is_approver": user_role_index(self.current_user, members) in APPROVER_ROLE_INDICES,
            "is_manager": user_role(self.current_user, members) == "manager",
            "role": user_role(self.current_user, members),
        }

        self.render(
            "group-requests.html",
            group=group,
            requests=requests,
            members=members,
            status=status,
            statuses=REQUEST_STATUS_CHOICES,
            offset=offset,
            limit=limit,
            total=total,
            current_user_role=current_user_role,
        )
