from typing import TYPE_CHECKING

from grouper.graph import Graph, NoSuchGroup
from grouper.models.group import Group

if TYPE_CHECKING:
    from typing import List  # noqa
    from grouper.models.base.session import Session  # noqa


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


def get_audited_groups(session):
    # type: (Session) -> List[Group]
    """Returns all audited enabled groups.

    At present, this is not cached at all and returns the full list of
    groups from the database each time it's called.

    Args:
        session (Session): Session to load data on.

    Returns:
        a list of all enabled and audited Group objects in the database
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
