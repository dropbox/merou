from datetime import datetime
import json

from grouper.models.base.constants import OBJ_TYPES
from grouper.models.comment import Comment
from grouper.models.counter import Counter
from grouper.models.group_edge import GROUP_EDGE_ROLES, GroupEdge
from grouper.models.request import Request
from grouper.models.request_status_change import RequestStatusChange


class InvalidRoleForMember(Exception):
    """This exception is raised when trying to set the role for a member of a group, but that
    member is not permitted to hold that role in the group"""
    pass


class MemberNotFound(Exception):
    """This exception is raised when trying to perform a group operation on an account that is
       not a member of the group."""
    pass


def _serialize_changes(edge, **updates):
    changes = {}
    for key, value in updates.items():
        if key not in ("role", "expiration", "active"):
            continue
        if getattr(edge, key) != value:
            if key == "expiration":
                changes[key] = value.strftime("%m/%d/%Y") if value else ""
            else:
                changes[key] = value
    return json.dumps(changes)


def _validate_role(member_type, requested_role):
    # type: (int, str) -> None
    if member_type == OBJ_TYPES["Group"] and requested_role != "member":
        raise InvalidRoleForMember("Groups can only have the role of 'member'")


def _get_edge(session, group, member):
    return GroupEdge.get(
        session,
        group_id=group.id,
        member_type=member.member_type,
        member_pk=member.id
    )


def _create_edge(session, group, member, role):
    edge, new = GroupEdge.get_or_create(
        session,
        group_id=group.id,
        member_type=member.member_type,
        member_pk=member.id
    )

    if new:
        # TODO(herb): this means all requests by this user to this group will
        # have the same role. we should probably record the role specifically
        # on the request and use that as the source on the UI
        edge._role = GROUP_EDGE_ROLES.index(role)

    session.flush()

    return edge


def persist_group_member_changes(session, group, requester, member, status, reason,
                                 create_edge=False, **updates):
    requested_at = datetime.utcnow()

    role = updates.get("role", "member")

    if "role" in updates:
        _validate_role(member.member_type, role)

    if create_edge:
        edge = _create_edge(session, group, member, role)
    else:
        edge = _get_edge(session, group, member)
        if not edge:
            raise MemberNotFound()

    changes = _serialize_changes(edge, **updates)

    request = Request(
        requester_id=requester.id,
        requesting_id=group.id,
        on_behalf_obj_type=member.member_type,
        on_behalf_obj_pk=member.id,
        requested_at=requested_at,
        edge_id=edge.id,
        status=status,
        changes=changes,
    ).add(session)
    session.flush()

    request_status_change = RequestStatusChange(
        request=request,
        user_id=requester.id,
        to_status=status,
        change_at=requested_at,
    ).add(session)
    session.flush()

    Comment(
        obj_type=OBJ_TYPES["RequestStatusChange"],
        obj_pk=request_status_change.id,
        user_id=requester.id,
        comment=reason,
        created_on=requested_at,
    ).add(session)
    session.flush()

    if status == "actioned":
        edge.apply_changes(request)
        session.flush()

    Counter.incr(session, "updates")

    return request
