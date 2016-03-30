from datetime import datetime

from sqlalchemy import or_

from grouper.model_soup import Group, GroupEdge


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
