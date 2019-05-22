from typing import TYPE_CHECKING

from grouper.graph import Graph, NoSuchGroup
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


def get_audited_groups(session):
    # type: (Session) -> List[Group]
    """Returns all audited enabled groups.

    At present, this is not cached at all and returns the full list of groups from the database
    each time it's called.
    """
    audited_groups = []
    graph = Graph()
    for group in get_all_groups(session):
        try:
            group_md = graph.get_group_details(group.name)
        except NoSuchGroup:
            # Very new group with no metadata yet, or it has been disabled and
            # excluded from in-memory cache.
            continue

        if group_md.get("audited", False):
            audited_groups.append(group)

    return audited_groups
