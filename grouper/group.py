from typing import TYPE_CHECKING

from grouper.models.group import Group

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import List


def get_all_groups(session):
    # type: (Session) -> List[Group]
    """Returns all enabled groups.

    At present, this is not cached at all and returns the full list of groups from the database
    each time it's called.
    """
    return session.query(Group).filter(Group.enabled == True)
