from typing import TYPE_CHECKING

from grouper.entities.group import Group, GroupJoinPolicy
from grouper.models.group import Group as SQLGroup
from grouper.models.user import User as SQLUser

if TYPE_CHECKING:
    from grouper.models.base.session import Session
    from typing import Optional


class GroupRepository:
    """Storage layer for groups."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def create_group(self, name, description, join_policy, email):
        # type: (str, str, GroupJoinPolicy, Optional[str]) -> None
        group = SQLGroup(
            groupname=name, description=description, canjoin=join_policy.value, email_address=email
        )
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
            description=group.description,
            email_address=group.email_address,
            join_policy=GroupJoinPolicy(group.canjoin),
            enabled=group.enabled,
            is_role_user=is_role_user,
        )
