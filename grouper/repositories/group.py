from typing import TYPE_CHECKING

from grouper.entities.group import Group, GroupJoinPolicy
from grouper.models.group import Group as SQLGroup
from grouper.models.user import User as SQLUser

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
        user = SQLUser.get(self.session, name=name)
        is_role_user = user.role_user if user else False
        return Group(
            name=group.groupname,
            id=group.id,
            description=group.description,
            email_address=group.email_address,
            join_policy=GroupJoinPolicy(group.canjoin),
            enabled=group.enabled,
            is_role_user=is_role_user,
        )
