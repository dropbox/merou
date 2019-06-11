from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import label

from grouper.models.base.constants import OBJ_TYPES_IDX, REQUEST_STATUS_CHOICES
from grouper.models.base.model_base import Model
from grouper.models.base.session import flush_transaction
from grouper.models.comment import Comment, CommentObjectMixin
from grouper.models.counter import Counter
from grouper.models.group_edge import GroupEdge
from grouper.models.json_encoded_type import JsonEncodedType
from grouper.models.request_status_change import RequestStatusChange
from grouper.models.user import User
from grouper.settings import settings
from grouper.util import reference_id


class Request(Model, CommentObjectMixin):
    # TODO: Extract business logic from this class
    # PLEASE DON'T ADD NEW BUSINESS LOGIC HERE IF YOU CAN AVOID IT!

    __tablename__ = "requests"

    id = Column(Integer, primary_key=True)

    # The User that made the request.
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requester = relationship("User", backref="requests", foreign_keys=[requester_id])

    # The Group the requester is requesting access to.
    requesting_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    requesting = relationship("Group", backref="requests", foreign_keys=[requesting_id])

    # The User/Group which will become a member of the requested resource.
    on_behalf_obj_type = Column(Integer, nullable=False)
    on_behalf_obj_pk = Column(Integer, nullable=False)

    edge_id = Column(Integer, ForeignKey("group_edges.id"), nullable=False)
    edge = relationship("GroupEdge", backref="requests")

    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    status = Column(Enum(*REQUEST_STATUS_CHOICES), default="pending", nullable=False)

    changes = Column(JsonEncodedType, nullable=False)

    @property
    def reference_id(self):
        # type: () -> str
        return reference_id(settings(), "group", self)

    def my_status_updates(self):
        requests = self.session.query(
            Request.id,
            RequestStatusChange.change_at,
            RequestStatusChange.from_status,
            RequestStatusChange.to_status,
            label("changed_by", User.username),
            label("reason", Comment.comment),
        ).filter(
            RequestStatusChange.user_id == User.id,
            Request.id == RequestStatusChange.request_id,
            Comment.obj_type == 3,
            Comment.obj_pk == RequestStatusChange.id,
            Request.id == self.id,
        )

        return requests

    @flush_transaction
    def update_status(self, requester, status, reason):
        # type: (User, str, str) -> None
        now = datetime.utcnow()
        current_status = self.status
        self.status = status

        request_status_change = RequestStatusChange(
            request=self,
            user_id=requester.id,
            from_status=current_status,
            to_status=status,
            change_at=now,
        ).add(self.session)
        self.session.flush()

        Comment(
            obj_type=OBJ_TYPES_IDX.index("RequestStatusChange"),
            obj_pk=request_status_change.id,
            user_id=requester.id,
            comment=reason,
            created_on=now,
        ).add(self.session)

        if status == "actioned":
            edge = self.session.query(GroupEdge).filter_by(id=self.edge_id).one()
            edge.apply_changes(self.changes)

        Counter.incr(self.session, "updates")
