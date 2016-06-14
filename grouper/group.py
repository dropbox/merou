from datetime import datetime

from sqlalchemy import or_

from grouper.model_soup import Group, GroupEdge, OWNER_ROLE_INDICES


def get_all_groups(session):
    """Returns all enabled groups.

    At present, this is not cached at all and returns the full list of
    groups from the database each time it's called.

    Args:
        session (Session): Session to load data on.

    Returns:
        a list of all Group objects in the database
    """
    return session.query(Group).filter(Group.enabled == True)


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
    if user_role_index(user, members) in OWNER_ROLE_INDICES:
        return True
    return False
