from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import or_

from grouper.entities.group_edge import GROUP_EDGE_ROLES
from grouper.models.base.constants import OBJ_TYPES
from grouper.models.group import Group
from grouper.models.group_edge import GroupEdge
from grouper.models.user import User
from grouper.repositories.interfaces import GroupEdgeRepository

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.models.base.session import Session
    from typing import List


class GraphGroupEdgeRepository(GroupEdgeRepository):
    """Graph-aware storage layer for group edges."""

    def __init__(self, graph):
        # type: (GroupGraph) -> None
        self.graph = graph

    def groups_of_user(self, username):
        # type: (str) -> List[str]
        user_details = self.graph.get_user_details(username)
        return list(user_details["groups"].keys())


class SQLGroupEdgeRepository(GroupEdgeRepository):
    """Pure SQL storage layer for group edges."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def groups_of_user(self, username):
        # type: (str) -> List[str]
        now = datetime.utcnow()
        user = User.get(self.session, name=username)
        if not user or user.role_user or user.is_service_account or not user.enabled:
            return []
        groups = (
            self.session.query(Group.groupname)
            .join(GroupEdge, Group.id == GroupEdge.group_id)
            .join(User, User.id == GroupEdge.member_pk)
            .filter(
                Group.enabled == True,
                User.id == user.id,
                GroupEdge.active == True,
                GroupEdge.member_type == OBJ_TYPES["User"],
                GroupEdge._role != GROUP_EDGE_ROLES.index("np-owner"),
                or_(GroupEdge.expiration > now, GroupEdge.expiration == None),
            )
            .distinct()
        )
        return [g.groupname for g in groups]
