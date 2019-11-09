from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import or_

from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge, OWNER_ROLE_INDICES

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from grouper.models.user import User
    from typing import List, Tuple


def get_groups_by_user(session, user):
    # type: (Session, User) -> List[Tuple[Group, GroupEdge]]
    """Return groups a given user is a member of along with the associated GroupEdge."""
    now = datetime.utcnow()
    return (
        session.query(Group, GroupEdge)
        .filter(
            GroupEdge.group_id == Group.id,
            GroupEdge.member_pk == user.id,
            GroupEdge.member_type == 0,
            GroupEdge.active == True,
            Group.enabled == True,
            or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
        )
        .all()
    )


def user_can_manage_group(session, group, user):
    # type: (Session, Group, User) -> bool
    """Determine if this user can manage the given group

    This returns true if this user object is a manager, owner, or np-owner of the given group.
    """
    from grouper.user import user_role

    if not group:
        return False
    members = group.my_members()
    if user_role(user, members) in ("owner", "np-owner", "manager"):
        return True
    return False


def user_is_owner_of_group(session, group, user):
    # type: (Session, Group, User) -> bool
    """Determine if this user is an owner of the given group

    This returns true if this user object is an owner or np-owner of the given group.
    """
    from grouper.user import user_role_index

    if not group:
        return False
    members = group.my_members()
    return user_role_index(user, members) in OWNER_ROLE_INDICES
