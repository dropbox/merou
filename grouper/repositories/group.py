from typing import TYPE_CHECKING

from grouper.entities.group import Group, GroupJoinPolicy
from grouper.models.group import Group as SQLGroup

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Optional


class GroupRepository(object):
    """Storage layer for groups."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def create_group(self, name, description, join_policy):
        # type: (str, str, GroupJoinPolicy) -> None
        group = SQLGroup(groupname=name, description=description, canjoin=join_policy.value)
        group.add(self.session)

    def get_group(self, name):
        # type: (str) -> Optional[Group]
        group = SQLGroup.get(self.session, name=name)
        if not group:
            return None
        return Group(
            name=group.groupname,
            description=group.description,
            join_policy=GroupJoinPolicy(group.canjoin),
        )
