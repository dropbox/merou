from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session  # noqa

from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge, OWNER_ROLE_INDICES
from grouper.models.user import User  # noqa


def get_groups_by_user(session, user):
    """Return groups a given user is a member of along with the associated GroupEdge.

    Args:
        session(): database session
        user(models.User): model for user in question
    """
    now = datetime.utcnow()
    return session.query(Group, GroupEdge).filter(
            GroupEdge.group_id == Group.id,
            GroupEdge.member_pk == user.id,
            GroupEdge.member_type == 0,
            GroupEdge.active == True,
            Group.enabled == True,
            or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
            ).all()


def get_all_groups_by_user(session, user):
    # type: (Session, User) -> List[tuple[Group, int]]
    """Return groups a given user is a member of along with the user's role.

    This includes groups inherited from other groups, unlike get_groups_by_user.

    Args:
        session(): database session
        user(models.User): model for user in question
    """
    from grouper.graph import Graph
    grps = Graph().get_user_details(username=user.name)["groups"]
    groups = session.query(Group).filter(Group.name.in_(grps.keys())).all()
    return [(group, grps[group.name]["role"]) for group in groups]


def user_can_manage_group(session, group, user):
    """Determine if this user can manage the given group

    This returns true if this user object is a manager, owner, or np-owner of the given group.

    Args:
        group (Group): Group to check permissions against.

    Returns:
        bool: True or False on whether or not they can manage.
    """
    from grouper.user import user_role
    if not group:
        return False
    members = group.my_members()
    if user_role(user, members) in ("owner", "np-owner", "manager"):
        return True
    return False


def user_is_owner_of_group(session, group, user):
    """Determine if this user is an owner of the given group

    This returns true if this user object is an owner or np-owner of the given group.

    Args:
        group (Group): Group to check permissions against.

    Returns:
        bool: True or False on whether or not they can manage.
    """
    from grouper.user import user_role_index
    if not group:
        return False
    members = group.my_members()
    return user_role_index(user, members) in OWNER_ROLE_INDICES
