from typing import TYPE_CHECKING

from sqlalchemy import literal
from sqlalchemy.sql import label

from grouper.models.comment import Comment
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.request import Request
from grouper.models.request_status_change import RequestStatusChange
from grouper.models.user import User

if TYPE_CHECKING:
    from typing import Optional
    from sqlalchemy.orm import Query, Session


def get_requests_by_group(session, group, status=None, user=None):
    # type: (Session, Group, Optional[str], Optional[User]) -> Query
    members = (
        session.query(
            label("type", literal(1)), label("id", Group.id), label("name", Group.groupname)
        )
        .union(
            session.query(
                label("type", literal(0)), label("id", User.id), label("name", User.username)
            )
        )
        .subquery()
    )

    requests = session.query(
        Request.id,
        Request.requested_at,
        Request.changes,
        label("role", GroupEdge._role),
        Request.status,
        label("requester", User.username),
        label("type", members.c.type),
        label("requesting", members.c.name),
        label("reason", Comment.comment),
    ).filter(
        Request.on_behalf_obj_pk == members.c.id,
        Request.on_behalf_obj_type == members.c.type,
        Request.requesting_id == group.id,
        Request.requester_id == User.id,
        Request.id == RequestStatusChange.request_id,
        RequestStatusChange.from_status == None,
        GroupEdge.id == Request.edge_id,
        Comment.obj_type == 3,
        Comment.obj_pk == RequestStatusChange.id,
    )

    if status:
        requests = requests.filter(Request.status == status)

    if user:
        requests = requests.filter(
            Request.on_behalf_obj_pk == user.id, Request.on_behalf_obj_type == 0
        )

    return requests


def count_requests_by_group(session, group, status=None, user=None):
    # type: (Session, Group, Optional[str], Optional[User]) -> int
    requests = session.query(Request).filter(Request.requesting_id == group.id)

    if status:
        requests = requests.filter(Request.status == status)

    if user:
        requests = requests.filter(
            Request.on_behalf_obj_pk == user.id, Request.on_behalf_obj_type == 0
        )

    return requests.count()
