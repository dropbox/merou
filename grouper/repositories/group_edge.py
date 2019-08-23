import itertools
from datetime import datetime
from typing import TYPE_CHECKING

from six import iteritems
from sqlalchemy import desc, or_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.util import aliased
from sqlalchemy.sql import label, literal

from grouper.entities.group import MemberInfo
from grouper.entities.group_edge import APPROVER_ROLE_INDICES, GROUP_EDGE_ROLES, OWNER_ROLE_INDICES
from grouper.models.base.constants import OBJ_TYPES
from grouper.models.group import Group as SQLGroup
from grouper.models.group_edge import GroupEdge as SQLGroupEdge
from grouper.models.user import User as SQLUser
from grouper.repositories.interfaces import GroupEdgeRepository

if TYPE_CHECKING:
    from grouper.graph import GroupGraph
    from grouper.models.base.session import Session
    from typing import List, Optional


class GraphGroupEdgeRepository(GroupEdgeRepository):
    """Graph-aware storage layer for group edges."""

    def __init__(self, graph):
        # type: (GroupGraph) -> None
        self.graph = graph

    def groups_of_user(self, username):
        # type: (str) -> List[str]
        user_details = self.graph.get_user_details(username)
        return list(user_details["groups"].keys())

    def direct_groups_of_user(self, username):
        # type: (str) -> List[str]
        user_details = self.graph.get_user_details(username)
        return list(
            [name for name, info in iteritems(user_details["groups"]) if info["distance"] == 1]
        )

    def _user_role_in_group(self, username, groupname):
        # type: (str, str) -> Optional[int]
        user_details = self.graph.get_user_details(username)
        try:
            return user_details["groups"][groupname]["role"]
        except KeyError:
            return None

    def user_is_owner_of_group(self, username, groupname):
        # type: (str, str) -> bool
        return self._user_role_in_group(username, groupname) in OWNER_ROLE_INDICES

    def user_is_approver_of_group(self, username, groupname):
        # type: (str, str) -> bool
        return self._user_role_in_group(username, groupname) in APPROVER_ROLE_INDICES

    def user_role_in_group(self, username, groupname):
        # type: (str, str) -> Optional[str]
        role_int = self._user_role_in_group(username, groupname)
        return GROUP_EDGE_ROLES[role_int] if role_int else None

    def group_members(self, groupname):
        # type: (str) -> List[MemberInfo]
        raise NotImplementedError


class SQLGroupEdgeRepository(GroupEdgeRepository):
    """Pure SQL storage layer for group edges."""

    def __init__(self, session):
        # type: (Session) -> None
        self.session = session

    def groups_of_user(self, username):
        raise NotImplementedError

    def direct_groups_of_user(self, username):
        # type: (str) -> List[str]
        now = datetime.utcnow()
        user = SQLUser.get(self.session, name=username)
        if not user or user.role_user or user.is_service_account or not user.enabled:
            return []
        groups = (
            self.session.query(SQLGroup.groupname)
            .join(SQLGroupEdge, SQLGroup.id == SQLGroupEdge.group_id)
            .join(SQLUser, SQLUser.id == SQLGroupEdge.member_pk)
            .filter(
                SQLGroup.enabled == True,
                SQLUser.id == user.id,
                SQLGroupEdge.active == True,
                SQLGroupEdge.member_type == OBJ_TYPES["User"],
                SQLGroupEdge._role != GROUP_EDGE_ROLES.index("np-owner"),
                or_(SQLGroupEdge.expiration > now, SQLGroupEdge.expiration == None),
            )
            .distinct()
        )
        return [g.groupname for g in groups]

    def _user_role_in_group(self, username, groupname):
        # type: (str, str) -> Optional[int]
        try:
            return (
                self.session.query(SQLGroupEdge._role)
                .filter(
                    SQLGroup.groupname == groupname,
                    SQLGroupEdge.group_id == SQLGroup.id,
                    SQLUser.username == username,
                    SQLGroupEdge.member_pk == SQLUser.id,
                    SQLGroupEdge.member_type == OBJ_TYPES["User"],
                )
                .one()
                ._role
            )
        except NoResultFound:
            return None

    def user_role_in_group(self, username, groupname):
        # type: (str, str) -> Optional[str]
        role_int = self._user_role_in_group(username, groupname)
        return GROUP_EDGE_ROLES[role_int] if role_int else None

    def user_is_owner_of_group(self, username, groupname):
        # type: (str, str) -> bool
        return self._user_role_in_group(username, groupname) in OWNER_ROLE_INDICES

    def user_is_approver_of_group(self, username, groupname):
        # type: (str, str) -> bool
        return self._user_role_in_group(username, groupname) in APPROVER_ROLE_INDICES

    def group_members(self, groupname):
        # type: (str) -> List[MemberInfo]
        parent = aliased(SQLGroup)
        group_member = aliased(SQLGroup)
        user_member = aliased(SQLUser)

        now = datetime.utcnow()

        member_users = (
            self.session.query(
                label("id", user_member.id),
                label("type", literal("User")),
                label("name", user_member.username),
                label("role", SQLGroupEdge._role),
                label("edge_id", SQLGroupEdge.id),
                label("expiration", SQLGroupEdge.expiration),
                label("role_user", user_member.role_user),
                label("is_service_account", user_member.is_service_account),
            )
            .filter(
                parent.groupname == groupname,
                parent.id == SQLGroupEdge.group_id,
                user_member.id == SQLGroupEdge.member_pk,
                SQLGroupEdge.active == True,
                parent.enabled == True,
                user_member.enabled == True,
                or_(SQLGroupEdge.expiration > now, SQLGroupEdge.expiration == None),
                SQLGroupEdge.member_type == 0,
            )
            .order_by(desc("role"), "name")
            .all()
        )

        member_groups = (
            self.session.query(
                label("id", group_member.id),
                label("type", literal("Group")),
                label("name", group_member.groupname),
                label("role", SQLGroupEdge._role),
                label("edge_id", SQLGroupEdge.id),
                label("expiration", SQLGroupEdge.expiration),
                label("role_user", literal(False)),
                label("is_service_account", literal(False)),
            )
            .filter(
                parent.groupname == groupname,
                parent.id == SQLGroupEdge.group_id,
                group_member.id == SQLGroupEdge.member_pk,
                SQLGroupEdge.active == True,
                parent.enabled == True,
                group_member.enabled == True,
                or_(SQLGroupEdge.expiration > now, SQLGroupEdge.expiration == None),
                SQLGroupEdge.member_type == 1,
            )
            .order_by(desc("role"), "name")
            .all()
        )

        return [
            MemberInfo(
                name=member.name,
                type=member.type,
                membership_id=member.edge_id,
                membership_role=GROUP_EDGE_ROLES[member.role],
                membership_expiration=member.expiration,
                role_user=member.role_user,
                is_service_account=member.is_service_account,
            )
            for member in itertools.chain(member_users, member_groups)
        ]

    def direct_parent_groups(self, groupname):
        # type: (str) -> List[str]
        parent = aliased(SQLGroup)
        me = aliased(SQLGroup)
        now = datetime.utcnow()
        groups = self.session.query(
            label("name", parent.groupname), label("role", SQLGroupEdge._role)
        ).filter(
            me.name == groupname,
            SQLGroupEdge.group_id == parent.id,
            SQLGroupEdge.member_pk == me.id,
            SQLGroupEdge.member_type == OBJ_TYPES["Group"],
            SQLGroupEdge.active == True,
            me.enabled == True,
            parent.enabled == True,
            or_(SQLGroupEdge.expiration > now, SQLGroupEdge.expiration == None),
        )
        return [g.name for g in groups]
