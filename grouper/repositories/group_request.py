from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import aliased
from sqlalchemy.sql import label

from grouper.entities.group_request import UserGroupRequest, UserGroupRequestNotFoundException
from grouper.entities.user import UserNotFoundException
from grouper.models.base.constants import OBJ_TYPES
from grouper.models.comment import Comment
from grouper.models.group import Group
from grouper.models.request import Request
from grouper.models.request_status_change import RequestStatusChange
from grouper.models.user import User

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.usecases.authorization import Authorization
    from typing import List


class GroupRequestRepository:
    """SQL storage layer for requests to join groups."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def cancel_user_request(self, user_request, reason, authorization):
        # type: (UserGroupRequest, str, Authorization) -> None
        now = datetime.utcnow()
        request = Request.get(self.session, id=user_request.id)
        if not request:
            raise UserGroupRequestNotFoundException(request)
        actor = User.get(self.session, name=authorization.actor)
        if not actor:
            raise UserNotFoundException(authorization.actor)

        request_status_change = RequestStatusChange(
            request=request,
            user_id=actor.id,
            from_status=request.status,
            to_status="cancelled",
            change_at=now,
        ).add(self.session)

        request.status = "cancelled"
        self.session.flush()

        Comment(
            obj_type=OBJ_TYPES["RequestStatusChange"],
            obj_pk=request_status_change.id,
            user_id=actor.id,
            comment=reason,
            created_on=now,
        ).add(self.session)

    def pending_requests_for_user(self, user):
        # type: (str) -> List[UserGroupRequest]
        requester = aliased(User)
        on_behalf_of = aliased(User)
        sql_requests = self.session.query(
            Request.id,
            Request.status,
            label("requester", requester.username),
            Group.groupname,
            label("on_behalf_of", on_behalf_of.username),
        ).filter(
            Request.on_behalf_obj_type == OBJ_TYPES["User"],
            Request.on_behalf_obj_pk == on_behalf_of.id,
            Request.requester_id == requester.id,
            Request.requesting_id == Group.id,
            Request.status == "pending",
        )

        requests = []
        for sql_request in sql_requests:
            request = UserGroupRequest(
                id=sql_request.id,
                user=sql_request.on_behalf_of,
                group=sql_request.groupname,
                requester=sql_request.requester,
                status=sql_request.status,
            )
            requests.append(request)
        return requests
